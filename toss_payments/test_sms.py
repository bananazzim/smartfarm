import json
import hashlib
import hmac
from datetime import datetime, timezone as datetime_timezone
from datetime import date, time
from email.message import Message
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from django.test import TestCase, override_settings
from django.core.management import call_command
from django.core.management.base import CommandError
from io import StringIO
from django.utils import timezone

from .models import PaymentOrder
from .sms import send_paid_order_sms, sync_sms_status, AUTH_ERROR_REASONS


@override_settings(SOLAPI_SMS_ENABLED=True, SOLAPI_API_KEY="fake-key",
                   SOLAPI_API_SECRET="fake-secret", SOLAPI_SENDER_NUMBER="02-1234-5678")
class ReservationSMSTests(TestCase):
    def setUp(self):
        self.order = PaymentOrder.objects.create(order_number="sms-test", product_name="GSO", amount=30000,
            status="paid", payment_key="fake-payment", payment_completed_at=timezone.now(),
            customer_phone="010-1234-5678", consulting_date=date(2027, 1, 2), consulting_time=time(14, 30))
        self.network = patch("toss_payments.sms.urlopen")
        self.http = self.network.start()
        self.addCleanup(self.network.stop)

    def status(self):
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "paid")
        return self.order.sms_status

    def accepted(self):
        self.http.return_value = BytesIO(b'{"messageList":[{"messageId":"M123","statusCode":"2000"}]}')

    def test_acceptance_is_not_delivery_and_duplicate_is_blocked(self):
        self.accepted()
        self.assertTrue(send_paid_order_sms(self.order))
        self.assertEqual(self.status(), "accepted")
        self.assertIsNone(self.order.sms_sent_at)
        request = self.http.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.solapi.com/messages/v4/send-many/detail")
        payload = json.loads(request.data)
        message = payload["messages"][0]
        self.assertEqual(message["to"], "01012345678")
        self.assertEqual(message["type"], "LMS")
        self.assertFalse(payload["allowDuplicates"])
        self.assertIn("결제금액: 30,000원", message["text"])
        self.assertNotIn("sms-test", message["text"])
        self.assertFalse(send_paid_order_sms(self.order))
        self.assertFalse(send_paid_order_sms(self.order, retry=True))
        self.http.assert_called_once()

    @override_settings(SOLAPI_SMS_ENABLED=False)
    def test_disabled_never_contacts_provider(self):
        self.assertFalse(send_paid_order_sms(self.order))
        self.assertEqual(self.status(), "disabled")
        self.http.assert_not_called()

    def test_ineligible_orders_never_contact_provider(self):
        for field, value in [("status", "pending"), ("payment_key", None), ("payment_completed_at", None),
                             ("customer_phone", ""), ("consulting_date", None), ("consulting_time", None)]:
            with self.subTest(field=field):
                old = getattr(self.order, field)
                PaymentOrder.objects.filter(pk=self.order.pk).update(**{field: value})
                self.assertFalse(send_paid_order_sms(self.order))
                PaymentOrder.objects.filter(pk=self.order.pk).update(**{field: old})
        self.http.assert_not_called()

    def test_invalid_phone_is_recorded_without_network(self):
        self.order.customer_phone = "010-abc-5678"
        self.order.save()
        self.assertFalse(send_paid_order_sms(self.order))
        self.assertEqual(self.status(), "failed")
        self.http.assert_not_called()

    def test_auth_failure_can_be_explicitly_retried(self):
        self.http.side_effect = HTTPError("https://api.solapi.com", 401, "secret", {}, None)
        self.assertFalse(send_paid_order_sms(self.order))
        self.assertEqual(self.status(), "failed")
        self.assertNotIn("secret", self.order.sms_error)
        self.http.side_effect = None
        self.accepted()
        self.assertFalse(send_paid_order_sms(self.order))
        self.assertTrue(send_paid_order_sms(self.order, retry=True))
        self.assertEqual(self.status(), "accepted")
        self.assertEqual(self.order.sms_attempts, 2)

    def test_auth_header_uses_utc_date_random_salt_and_documented_hmac(self):
        fixed = datetime(2026, 10, 26, 3, 4, 5, tzinfo=datetime_timezone.utc)
        salt = "0123456789abcdef0123456789abcdef"
        self.accepted()
        with patch("toss_payments.sms.timezone.now", return_value=fixed), patch(
            "toss_payments.sms.secrets.token_hex", return_value=salt
        ) as nonce:
            self.assertTrue(send_paid_order_sms(self.order))
        date_text = "2026-10-26T03:04:05Z"
        expected = hmac.new(b"fake-secret", (date_text + salt).encode(), hashlib.sha256).hexdigest()
        header = self.http.call_args.args[0].get_header("Authorization")
        # Boolean comparison avoids exposing a header in failed assertion output.
        self.assertTrue(header == f"HMAC-SHA256 apiKey=fake-key, date={date_text}, salt={salt}, signature={expected}")
        nonce.assert_called_once_with(16)


    def test_403_extracts_known_code_but_never_persists_raw_reason(self):
        for code in AUTH_ERROR_REASONS:
            with self.subTest(code=code):
                PaymentOrder.objects.filter(pk=self.order.pk).update(sms_status="pending")
                body = json.dumps({"errorCode": code, "errorMessage":
                    "fake-key fake-secret 01012345678 Authorization signature=private"}).encode()
                self.http.side_effect = HTTPError("https://api.solapi.com", 403, "", {}, BytesIO(body))
                self.assertFalse(send_paid_order_sms(self.order))
                self.assertEqual(self.status(), "failed")
                self.assertIn(f"code={code}", self.order.sms_error)
                for sensitive in ("fake-key", "fake-secret", "01012345678", "private"):
                    self.assertNotIn(sensitive, self.order.sms_error)

    def test_403_unknown_malformed_and_oversized_responses_are_not_stored(self):
        for body in (b"not-json", b"[]", b'{"errorCode": {}}',
                     b'{"errorCode":"fake-secret","errorMessage":"01012345678"}', b"x" * 9000):
            with self.subTest(length=len(body)):
                PaymentOrder.objects.filter(pk=self.order.pk).update(sms_status="pending")
                self.http.side_effect = HTTPError("https://api.solapi.com", 403, "", {}, BytesIO(body))
                self.assertFalse(send_paid_order_sms(self.order))
                self.assertEqual(self.status(), "failed")
                self.assertIn("code=unrecognized", self.order.sms_error)
                self.assertNotIn("fake-secret", self.order.sms_error)
                self.assertNotIn("01012345678", self.order.sms_error)

    def test_uncertain_requests_block_retries(self):
        for response in [TimeoutError(), ValueError(), HTTPError("https://api.solapi.com", 500, "", {}, None)]:
            with self.subTest(response=type(response).__name__):
                PaymentOrder.objects.filter(pk=self.order.pk).update(sms_status="pending")
                self.http.side_effect = response
                self.assertFalse(send_paid_order_sms(self.order))
                self.assertEqual(self.status(), "unknown")
                calls = self.http.call_count
                self.assertFalse(send_paid_order_sms(self.order, retry=True))
                self.assertEqual(calls, self.http.call_count)

    def test_delivery_lookup_marks_only_confirmed_success(self):
        self.accepted()
        send_paid_order_sms(self.order)
        self.http.return_value = BytesIO(b'{"messageList":{"M123":{"status":"COMPLETE","statusCode":"4000"}}}')
        self.assertTrue(sync_sms_status(self.order))
        self.assertEqual(self.status(), "sent")
        self.assertIsNotNone(self.order.sms_sent_at)
        self.assertEqual(self.http.call_args.args[0].get_method(), "GET")

    def test_lookup_failure_preserves_acceptance(self):
        self.accepted()
        send_paid_order_sms(self.order)
        self.http.side_effect = TimeoutError()
        self.assertFalse(sync_sms_status(self.order))
        self.assertEqual(self.status(), "accepted")

    def test_in_progress_claim_blocks_second_request(self):
        def concurrent(request, **kwargs):
            self.assertFalse(send_paid_order_sms(self.order))
            self.assertFalse(send_paid_order_sms(self.order, retry=True))
            return BytesIO(b'{"messageList":[{"messageId":"M123","statusCode":"2000"}]}')
        self.http.side_effect = concurrent
        self.assertTrue(send_paid_order_sms(self.order))
        self.http.assert_called_once()

    def test_disabled_order_requires_explicit_retry_after_enabling(self):
        with override_settings(SOLAPI_SMS_ENABLED=False):
            send_paid_order_sms(self.order)
        self.assertEqual(self.status(), "disabled")
        self.assertEqual(self.order.sms_attempts, 0)
        self.assertIsNone(self.order.sms_requested_at)
        self.assertFalse(send_paid_order_sms(self.order))
        self.http.assert_not_called()
        self.accepted()
        call_command("reservation_sms", "retry", self.order.order_number, stdout=StringIO())
        self.assertEqual(self.status(), "accepted")
        self.assertEqual(self.order.sms_attempts, 1)
        self.http.assert_called_once()

    def test_retry_command_dry_run_preserves_all_fields_and_other_orders(self):
        PaymentOrder.objects.filter(pk=self.order.pk).update(sms_status="disabled", sheets_delivery_status="sent")
        before = list(PaymentOrder.objects.values())
        call_command("reservation_sms", "retry", self.order.order_number, dry_run=True, stdout=StringIO())
        self.assertEqual(before, list(PaymentOrder.objects.values()))
        self.http.assert_not_called()

    def test_retry_command_requires_order_number(self):
        with self.assertRaises(CommandError):
            call_command("reservation_sms", "retry", stdout=StringIO())
        self.http.assert_not_called()

    def test_retry_command_blocks_non_paid_and_unsafe_sms_states(self):
        for status, sms_status in [("pending", "disabled"), ("failed", "failed"),
                                   ("processing", "disabled"), ("paid", "sent"),
                                   ("paid", "accepted"), ("paid", "sending"),
                                   ("paid", "unknown"), ("paid", "pending")]:
            with self.subTest(status=status, sms_status=sms_status):
                PaymentOrder.objects.filter(pk=self.order.pk).update(status=status, sms_status=sms_status)
                before = list(PaymentOrder.objects.values())
                with self.assertRaises(CommandError):
                    call_command("reservation_sms", "retry", self.order.order_number, stdout=StringIO())
                self.assertEqual(before, list(PaymentOrder.objects.values()))
        self.http.assert_not_called()

    @override_settings(SOLAPI_SMS_ENABLED=False)
    def test_retry_command_with_disabled_setting_does_not_change_database(self):
        PaymentOrder.objects.filter(pk=self.order.pk).update(sms_status="disabled")
        before = list(PaymentOrder.objects.values())
        with self.assertRaisesMessage(CommandError, "false in this process"):
            call_command("reservation_sms", "retry", self.order.order_number, stdout=StringIO())
        self.assertEqual(before, list(PaymentOrder.objects.values()))
        self.http.assert_not_called()

    def test_retry_only_targets_named_order_and_failure_preserves_sheets(self):
        PaymentOrder.objects.filter(pk=self.order.pk).update(sms_status="disabled",
            sheets_delivery_status="sent", sheets_delivery_error="", sheets_sent_at=timezone.now())
        other = PaymentOrder.objects.create(order_number="untouched", product_name="GSO", amount=30000,
            status="paid", sms_status="disabled")
        before = PaymentOrder.objects.values().get(pk=self.order.pk)
        other_before = PaymentOrder.objects.values().get(pk=other.pk)
        self.http.side_effect = HTTPError("https://api.solapi.com", 401, "", {}, None)
        call_command("reservation_sms", "retry", self.order.order_number, stdout=StringIO())
        self.assertEqual(self.status(), "failed")
        after = PaymentOrder.objects.values().get(pk=self.order.pk)
        for field in ("status", "payment_key", "payment_completed_at", "sheets_delivery_status",
                      "sheets_delivery_error", "sheets_sent_at"):
            self.assertEqual(before[field], after[field])
        self.assertEqual(other_before, PaymentOrder.objects.values().get(pk=other.pk))
        self.http.assert_called_once()


@override_settings(SOLAPI_API_KEY="fake-key", SOLAPI_API_SECRET="fake-secret")
class SolapiAuthDiagnosticTests(TestCase):
    def setUp(self):
        self.network = patch("toss_payments.management.commands.diagnose_solapi_auth.urlopen")
        self.http = self.network.start()
        self.addCleanup(self.network.stop)

    def response(self, status, content_type, body, **headers):
        response = MagicMock()
        response.__enter__.return_value = response
        response.getcode.return_value = status
        response.read.return_value = body
        response.headers = Message()
        response.headers["Content-Type"] = content_type
        for name, value in headers.items():
            response.headers[name.replace("_", "-")] = value
        return response

    def run_diagnostic(self, response=None, error=None):
        if error is not None:
            self.http.side_effect = error
        else:
            self.http.return_value = response
        output = StringIO()
        call_command("diagnose_solapi_auth", stdout=output)
        return output.getvalue()

    def test_success_uses_authenticated_read_only_get_and_hides_response_body(self):
        output = self.run_diagnostic(
            self.response(200, "application/json", b'{"messageList":{"sensitive":"hidden"}}')
        )
        request = self.http.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertTrue(request.full_url.startswith("https://api.solapi.com/messages/v4/list?limit=1"))
        self.assertTrue(request.get_header("Authorization").startswith("HMAC-SHA256 apiKey=fake-key"))
        self.assertIn("HTTP 상태 코드: 200", output)
        self.assertIn("응답 Content-Type: application/json", output)
        self.assertIn("읽기 전용 인증 요청 성공", output)
        self.assertNotIn("sensitive", output)
        self.assertNotIn("fake-key", output)
        self.assertNotIn("fake-secret", output)

    def test_api_403_shows_allowlisted_code_and_never_echoes_response_details(self):
        headers = Message()
        headers["Content-Type"] = "application/json"
        body = json.dumps({
            "errorCode": "Forbidden",
            "errorMessage": "fake-key fake-secret 01012345678 private signature",
        }).encode()
        error = HTTPError("https://api.solapi.com/messages/v4/list", 403, "", headers, BytesIO(body))
        output = self.run_diagnostic(error=error)
        self.assertIn("HTTP 상태 코드: 403", output)
        self.assertIn("API 오류 코드: Forbidden", output)
        self.assertIn("API Key 권한", output)
        self.assertIn("403 점검 항목:", output)
        for sensitive in ("fake-key", "fake-secret", "01012345678", "private signature"):
            self.assertNotIn(sensitive, output)
        request = self.http.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)

    def test_html_403_reports_intermediary_as_possible_not_proven(self):
        headers = Message()
        headers["Content-Type"] = "text/html"
        headers["Server"] = "nginx"
        headers["Via"] = "1.1 edge"
        error = HTTPError(
            "https://api.solapi.com/messages/v4/list",
            403,
            "",
            headers,
            BytesIO(b"<html>private details</html>"),
        )
        output = self.run_diagnostic(error=error)
        self.assertIn("응답 Content-Type: text/html", output)
        self.assertIn("중간 프록시/WAF", output)
        self.assertIn("Server, Via", output)
        self.assertNotIn("private details", output)
