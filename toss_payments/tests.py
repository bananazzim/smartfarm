import json
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import PaymentOrder
from .sheets import send_paid_order_to_sheets
from .views import PRODUCT_AMOUNT, PRODUCT_NAME


@override_settings(TOSS_CLIENT_KEY="test_ck_example", TOSS_SECRET_KEY="test_sk_example")
class PaymentOrderTests(TestCase):
    def setUp(self):
        super().setUp()
        # TestCase wraps requests in a transaction; exercise committed callbacks.
        patcher = patch("toss_payments.views.transaction.on_commit", side_effect=lambda callback: callback())
        patcher.start()
        self.addCleanup(patcher.stop)
        sms = patch("toss_payments.views.send_paid_order_sms")
        self.mock_sms = sms.start()
        self.addCleanup(sms.stop)

    def survey_data(self):
        return {
            "discovery_source": "youtube",
            "consulting_interest": "greenhouse_consulting",
            "investment_budget": "under_100k",
            "annual_revenue": "not_operating",
            "annual_profit": "",
        }

    def reservation_data(self):
        requested_at = timezone.localtime(timezone.now()) + timedelta(days=2)
        return {
            "customer_name": "홍길동",
            "customer_phone": "010-1234-5678",
            "consulting_date": requested_at.date().isoformat(),
            "consulting_time": requested_at.time().replace(second=0, microsecond=0).isoformat(),
            "greenhouse_location": "전북 김제시",
            "consulting_request": "상담 요청 내용",
            "privacy_consent": "on",
        }

    def create_order(self):
        order_data = self.survey_data()
        order_data.update(self.reservation_data())
        order_data["privacy_consent"] = True
        return PaymentOrder.objects.create(
            order_number="GSO-test-order",
            product_name=PRODUCT_NAME,
            amount=PRODUCT_AMOUNT,
            **order_data,
        )

    def toss_response(self, order):
        return BytesIO(
            json.dumps(
                {
                    "paymentKey": "test_payment_key",
                    "orderId": order.order_number,
                    "totalAmount": order.amount,
                    "status": "DONE",
                }
            ).encode()
        )

    def callback_url(self, order, **overrides):
        params = {
            "paymentKey": "test_payment_key",
            "orderId": order.order_number,
            "amount": str(order.amount),
        }
        params.update(overrides)
        return f"{reverse('toss_payments:payment_success')}?{urlencode(params)}"

    def test_start_page_requires_configured_keys_to_create_order(self):
        with override_settings(TOSS_CLIENT_KEY="", TOSS_SECRET_KEY=""):
            response = self.client.post(
                reverse("toss_payments:create_order"),
                self.survey_data(),
            )
        self.assertEqual(response.status_code, 503)
        self.assertFalse(PaymentOrder.objects.exists())

    @patch("toss_payments.views.send_paid_order_to_sheets", side_effect=RuntimeError("mock failure"))
    @patch("toss_payments.views.urlopen")
    def test_unexpected_sheets_failure_still_attempts_sms(self, toss, sheets):
        order = self.create_order()
        toss.return_value = self.toss_response(order)
        response = self.client.get(self.callback_url(order))
        order.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(order.status, "paid")
        self.mock_sms.assert_called_once()

    @patch("toss_payments.views.send_paid_order_to_sheets")
    @patch("toss_payments.views.urlopen")
    def test_unexpected_sms_failure_preserves_payment_and_sheets(self, toss, sheets):
        order = self.create_order()
        toss.return_value = self.toss_response(order)
        self.mock_sms.side_effect = RuntimeError("mock failure")
        response = self.client.get(self.callback_url(order))
        order.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(order.status, "paid")
        sheets.assert_called_once()

    def test_checkout_button_is_not_enabled_without_server_secret(self):
        order = self.create_order()
        with override_settings(TOSS_SECRET_KEY=""):
            response = self.client.get(
                reverse("toss_payments:checkout_order", kwargs={"order_number": order.order_number})
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "결제 설정을 확인할 수 없습니다.")
        self.assertNotContains(response, "id=\"payment-button\"")

    def test_order_creation_uses_server_product_and_amount(self):
        response = self.client.post(
            reverse("toss_payments:create_order"),
            self.survey_data(),
        )
        self.assertEqual(response.status_code, 302)
        order = PaymentOrder.objects.get()
        self.assertEqual(order.product_name, PRODUCT_NAME)
        self.assertEqual(order.amount, PRODUCT_AMOUNT)
        self.assertEqual(order.status, PaymentOrder.Status.PENDING)
        checkout_response = self.client.get(response.url)
        self.assertContains(checkout_response, "https://js.tosspayments.com/v2/standard")
        self.assertContains(checkout_response, "testserver/payments/success/")
        self.assertEqual(response.url, reverse(
            "toss_payments:checkout_order",
            kwargs={"order_number": order.order_number},
        ))
        self.assertEqual(order.discovery_source, "youtube")
        self.assertEqual(order.consulting_interest, "greenhouse_consulting")
        self.assertEqual(order.investment_budget, "under_100k")
        self.assertEqual(order.annual_revenue, "not_operating")
        self.assertEqual(order.annual_profit, "")

    def test_invalid_survey_does_not_create_order(self):
        response = self.client.post(reverse("toss_payments:create_order"))
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "필수 사전 설문", status_code=400)
        self.assertFalse(PaymentOrder.objects.exists())

    def test_reservation_is_saved_against_the_order_only_with_consent(self):
        order = PaymentOrder.objects.create(
            order_number="GSO-reservation",
            product_name=PRODUCT_NAME,
            amount=PRODUCT_AMOUNT,
            **self.survey_data(),
        )
        reservation_data = self.reservation_data()
        url = reverse(
            "toss_payments:save_reservation",
            kwargs={"order_number": order.order_number},
        )
        response = self.client.post(url, reservation_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        order.refresh_from_db()
        self.assertTrue(order.privacy_consent)
        self.assertEqual(order.customer_name, "홍길동")
        self.assertEqual(order.customer_phone, "010-1234-5678")
        self.assertEqual(order.greenhouse_location, "전북 김제시")
        self.assertEqual(order.consulting_request, "상담 요청 내용")
        self.assertEqual(order.discovery_source, "youtube")

        reservation_data.pop("privacy_consent")
        response = self.client.post(url, reservation_data)
        self.assertEqual(response.status_code, 400)
        unconsented_order = PaymentOrder.objects.create(
            order_number="GSO-no-consent",
            product_name=PRODUCT_NAME,
            amount=PRODUCT_AMOUNT,
            **self.survey_data(),
        )
        response = self.client.post(
            reverse(
                "toss_payments:save_reservation",
                kwargs={"order_number": unconsented_order.order_number},
            ),
            reservation_data,
        )
        self.assertEqual(response.status_code, 400)
        unconsented_order.refresh_from_db()
        self.assertFalse(unconsented_order.privacy_consent)
        self.assertEqual(unconsented_order.customer_name, "")

    @patch("toss_payments.views.urlopen")
    def test_amount_mismatch_never_calls_toss_or_marks_order_paid(self, mocked_urlopen):
        order = self.create_order()
        response = self.client.get(self.callback_url(order, amount="30001"))
        order.refresh_from_db()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(order.status, PaymentOrder.Status.PENDING)
        mocked_urlopen.assert_not_called()

    @patch("toss_payments.sheets.urlopen")
    @patch("toss_payments.views.send_paid_order_to_sheets")
    @patch("toss_payments.views.urlopen")
    def test_only_verified_confirmation_marks_order_paid_and_duplicate_is_idempotent(
        self, mocked_urlopen, mocked_delivery, mocked_sheets_urlopen
    ):
        order = self.create_order()
        mocked_urlopen.return_value = self.toss_response(order)

        response = self.client.get(self.callback_url(order))
        order.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "toss_payments/success.html")
        self.assertEqual(order.status, PaymentOrder.Status.PAID)
        self.assertEqual(order.payment_key, "test_payment_key")
        self.assertIsNotNone(order.payment_completed_at)
        mocked_delivery.assert_called_once_with(order)
        self.mock_sms.assert_called_once_with(order)

        duplicate_response = self.client.get(self.callback_url(order))
        self.assertEqual(duplicate_response.status_code, 200)
        self.assertTemplateUsed(duplicate_response, "toss_payments/success.html")
        mocked_urlopen.assert_called_once()
        mocked_delivery.assert_called_once()
        self.mock_sms.assert_called_once()
        mocked_sheets_urlopen.assert_not_called()

    @override_settings(
        GSO_SHEETS_WEBHOOK_URL="https://example.test/webhook",
        GSO_WEBHOOK_SECRET="test-webhook-secret",
    )
    @patch("toss_payments.sheets.urlopen")
    @patch("toss_payments.views.urlopen")
    def test_approved_payment_is_sent_to_sheets_using_saved_order_data(
        self, mocked_toss_urlopen, mocked_sheets_urlopen
    ):
        order = self.create_order()
        mocked_toss_urlopen.return_value = self.toss_response(order)
        mocked_sheets_urlopen.return_value = BytesIO(b'{"ok": true}')

        response = self.client.get(self.callback_url(order))

        order.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "홍길동")
        self.assertContains(response, "010-1234-5678")
        self.assertEqual(order.status, PaymentOrder.Status.PAID)
        self.assertEqual(order.sheets_delivery_status, PaymentOrder.SheetsDeliveryStatus.SENT)
        self.assertIsNotNone(order.sheets_sent_at)
        request = mocked_sheets_urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["order_id"], order.order_number)
        self.assertEqual(payload["customer_name"], order.customer_name)
        self.assertEqual(payload["phone"], order.customer_phone)
        self.assertEqual(payload["payment_amount"], PRODUCT_AMOUNT)
        self.assertEqual(payload["payment_status"], "DONE")
        self.assertEqual(payload["sms_status"], "미발송")
        self.assertEqual(payload["secret"], "test-webhook-secret")
        self.assertTrue(payload["paid_at"].endswith("+09:00"))
        self.assertEqual(payload["consultation_date"], order.consulting_date.isoformat())
        self.assertEqual(payload["consultation_time"], order.consulting_time.strftime("%H:%M"))
        self.assertEqual(
            list(payload),
            [
                "order_id",
                "paid_at",
                "customer_name",
                "phone",
                "consultation_date",
                "consultation_time",
                "greenhouse_location",
                "request_notes",
                "referral_source",
                "interest_area",
                "investment_budget",
                "annual_revenue",
                "annual_profit",
                "product_name",
                "payment_amount",
                "payment_status",
                "sms_status",
                "secret",
            ],
        )

    @patch("toss_payments.views.send_paid_order_to_sheets")
    @patch("toss_payments.views.urlopen")
    def test_order_without_saved_consent_never_reaches_toss_or_sheets(
        self, mocked_toss_urlopen, mocked_delivery
    ):
        order = self.create_order()
        order.privacy_consent = False
        order.save(update_fields=("privacy_consent",))

        response = self.client.get(self.callback_url(order))

        order.refresh_from_db()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(order.status, PaymentOrder.Status.PENDING)
        mocked_toss_urlopen.assert_not_called()
        mocked_delivery.assert_not_called()

    @override_settings(
        GSO_SHEETS_WEBHOOK_URL="https://example.test/webhook",
        GSO_WEBHOOK_SECRET="test-webhook-secret",
    )
    @patch("toss_payments.sheets.urlopen", return_value=BytesIO(b'{"ok": false}'))
    @patch("toss_payments.views.urlopen")
    def test_sheets_error_does_not_fail_verified_payment(
        self, mocked_toss_urlopen, mocked_sheets_urlopen
    ):
        order = self.create_order()
        mocked_toss_urlopen.return_value = self.toss_response(order)

        response = self.client.get(self.callback_url(order))

        order.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "toss_payments/success.html")
        self.assertEqual(order.status, PaymentOrder.Status.PAID)
        self.assertEqual(order.sheets_delivery_status, PaymentOrder.SheetsDeliveryStatus.FAILED)
        mocked_sheets_urlopen.assert_called_once()

    @patch("toss_payments.views.urlopen")
    @patch("toss_payments.views.send_paid_order_to_sheets")
    def test_mismatched_toss_confirmation_does_not_mark_order_paid(
        self, mocked_delivery, mocked_urlopen
    ):
        order = self.create_order()
        mocked_urlopen.return_value = BytesIO(
            json.dumps(
                {
                    "paymentKey": "different_key",
                    "orderId": order.order_number,
                    "totalAmount": order.amount,
                    "status": "DONE",
                }
            ).encode()
        )
        response = self.client.get(self.callback_url(order))
        order.refresh_from_db()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(order.status, PaymentOrder.Status.FAILED)
        mocked_delivery.assert_not_called()

    @patch("toss_payments.views.send_paid_order_to_sheets")
    @patch("toss_payments.views.urlopen")
    def test_toss_approval_failure_never_sends_to_sheets(
        self, mocked_urlopen, mocked_delivery
    ):
        order = self.create_order()
        mocked_urlopen.side_effect = HTTPError(
            "https://api.tosspayments.com/v1/payments/confirm",
            400,
            "rejected",
            {},
            BytesIO(b""),
        )

        response = self.client.get(self.callback_url(order))

        order.refresh_from_db()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(order.status, PaymentOrder.Status.FAILED)
        mocked_delivery.assert_not_called()

    @patch("toss_payments.views.urlopen")
    def test_toss_server_error_keeps_order_processing_to_prevent_duplicate_approval(
        self, mocked_urlopen
    ):
        order = self.create_order()
        mocked_urlopen.side_effect = HTTPError(
            "https://api.tosspayments.com/v1/payments/confirm",
            500,
            "server error",
            {},
            BytesIO(b""),
        )
        response = self.client.get(self.callback_url(order))
        order.refresh_from_db()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(order.status, PaymentOrder.Status.PROCESSING)

    def test_fail_redirect_does_not_trust_client_to_change_order_status(self):
        order = self.create_order()
        response = self.client.get(
            reverse("toss_payments:payment_fail"),
            {"orderId": order.order_number, "message": "forged"},
        )
        order.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(order.status, PaymentOrder.Status.PENDING)


@override_settings(
    GSO_SHEETS_WEBHOOK_URL="https://example.test/webhook",
    GSO_WEBHOOK_SECRET="test-webhook-secret",
)
class SheetsDeliveryTests(TestCase):
    def create_paid_order(self):
        requested_at = timezone.localtime(timezone.now()) + timedelta(days=2)
        return PaymentOrder.objects.create(
            order_number="GSO-sheets-order",
            product_name=PRODUCT_NAME,
            amount=PRODUCT_AMOUNT,
            status=PaymentOrder.Status.PAID,
            payment_completed_at=timezone.now(),
            discovery_source="youtube",
            consulting_interest="greenhouse_consulting",
            investment_budget="under_100k",
            customer_name="홍길동",
            customer_phone="010-1234-5678",
            consulting_date=requested_at.date(),
            consulting_time=requested_at.time().replace(second=0, microsecond=0),
            privacy_consent=True,
        )

    @patch("toss_payments.sheets.urlopen")
    def test_non_ok_apps_script_response_is_recorded_without_reversing_payment(
        self, mocked_urlopen
    ):
        order = self.create_paid_order()
        mocked_urlopen.return_value = BytesIO(b'{"ok": false}')

        sent = send_paid_order_to_sheets(order)

        order.refresh_from_db()
        self.assertFalse(sent)
        self.assertEqual(order.status, PaymentOrder.Status.PAID)
        self.assertEqual(order.sheets_delivery_status, PaymentOrder.SheetsDeliveryStatus.FAILED)
        self.assertIn("did not confirm", order.sheets_delivery_error)

    @patch("toss_payments.sheets.urlopen", side_effect=TimeoutError)
    def test_timeout_is_recorded_and_paid_status_is_preserved(self, mocked_urlopen):
        order = self.create_paid_order()

        sent = send_paid_order_to_sheets(order)

        order.refresh_from_db()
        self.assertFalse(sent)
        self.assertEqual(order.status, PaymentOrder.Status.PAID)
        self.assertEqual(order.sheets_delivery_status, PaymentOrder.SheetsDeliveryStatus.FAILED)
        self.assertIn("timed out", order.sheets_delivery_error)
        mocked_urlopen.assert_called_once()
        self.assertEqual(mocked_urlopen.call_args.kwargs["timeout"], 10)

    @override_settings(GSO_SHEETS_WEBHOOK_URL="", GSO_WEBHOOK_SECRET="")
    @patch("toss_payments.sheets.urlopen")
    def test_missing_webhook_environment_variables_are_recorded(
        self, mocked_urlopen
    ):
        order = self.create_paid_order()

        sent = send_paid_order_to_sheets(order)

        order.refresh_from_db()
        self.assertFalse(sent)
        self.assertEqual(order.sheets_delivery_status, PaymentOrder.SheetsDeliveryStatus.FAILED)
        self.assertIn("not configured", order.sheets_delivery_error)
        mocked_urlopen.assert_not_called()

    @patch("toss_payments.sheets.urlopen")
    def test_failed_delivery_can_be_retried(self, mocked_urlopen):
        order = self.create_paid_order()
        mocked_urlopen.side_effect = [URLError("offline"), BytesIO(b'{"ok": true}')]

        self.assertFalse(send_paid_order_to_sheets(order))
        order.refresh_from_db()
        self.assertEqual(order.sheets_delivery_status, PaymentOrder.SheetsDeliveryStatus.FAILED)

        self.assertTrue(send_paid_order_to_sheets(order))
        order.refresh_from_db()
        self.assertEqual(order.status, PaymentOrder.Status.PAID)
        self.assertEqual(order.sheets_delivery_status, PaymentOrder.SheetsDeliveryStatus.SENT)
        self.assertEqual(order.sheets_delivery_error, "")
        self.assertEqual(mocked_urlopen.call_count, 2)
