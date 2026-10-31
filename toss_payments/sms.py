"""Reservation LMS delivery. Uncertain requests are never automatically resent."""
import hashlib
import hmac
import json
import re
import secrets
from datetime import timezone as datetime_timezone
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.db.models import F
from django.utils import timezone

from .models import PaymentOrder

API_URL = "https://api.solapi.com/messages/v4"

# Never persist arbitrary provider text: it may echo keys, signatures or recipients.
AUTH_ERROR_REASONS = {
    "InvalidAPIKey": "유효하지 않은 API Key: 키 상태와 실행 환경 설정을 확인하세요.",
    "SignatureDoesNotMatch": "인증 서명 불일치: API Key와 Secret의 쌍을 확인하세요.",
    "RequestTimeTooSkewed": "요청 시간 차이 초과: 서버 시계를 동기화하세요.",
    "DuplicatedSignature": "인증 서명 중복: 요청별 salt 생성 여부를 확인하세요.",
}


def _safe_http_error(error):
    """Extract only allowlisted error codes and use local, non-sensitive reasons."""
    prefix = f"SolAPI HTTP {error.code}."
    try:
        body = json.loads(error.read(8192))
        code = body.get("errorCode") if isinstance(body, dict) else None
        if isinstance(code, str) and code in AUTH_ERROR_REASONS:
            return f"{prefix} code={code}; reason={AUTH_ERROR_REASONS[code]}"
    except (ValueError, TypeError, OSError, HTTPException):
        pass
    return prefix + " code=unrecognized; reason=오류 상세를 안전하게 분류할 수 없습니다."


def normalize_phone(value, *, sender=False):
    number = re.sub(r"[ -]", "", value)
    pattern = r"(?:02\d{7,8}|0[3-6][1-5]\d{7,8}|070\d{8}|01[016789]\d{7,8}|1[568]\d{6})" if sender else r"01[016789]\d{7,8}"
    if not re.fullmatch(pattern, number, flags=re.ASCII):
        raise ValueError("Invalid sender number." if sender else "Invalid customer phone number.")
    return number


def _authorization_header():
    date = timezone.now().astimezone(datetime_timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    salt = secrets.token_hex(16)
    signature = hmac.new(
        settings.SOLAPI_API_SECRET.encode(),
        (date + salt).encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"HMAC-SHA256 apiKey={settings.SOLAPI_API_KEY}, date={date}, salt={salt}, signature={signature}"


def reservation_message(order):
    return (
        "안녕하세요. GSO입니다.\n\n"
        "스마트팜 컨설팅 예약이 완료되었습니다.\n\n"
        f"주문자명: {order.customer_name or '미입력'}\n"
        f"연락처: {order.customer_phone or '미입력'}\n"
        f"예약일: {order.consulting_date:%Y-%m-%d}\n"
        f"예약시간: {order.consulting_time:%H:%M}\n"
        f"결제금액: {order.amount:,}원\n\n"
        "상담 신청해 주셔서 감사합니다."
    )


def _api(path, payload=None):
    request = Request(API_URL + path, data=json.dumps(payload).encode() if payload is not None else None,
                      headers={"Authorization": _authorization_header(),
                               "Content-Type": "application/json"})
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read(65536))


def send_paid_order_sms(order, *, retry=False):
    S = PaymentOrder.SMSStatus
    eligible = PaymentOrder.objects.filter(
        pk=order.pk, status=PaymentOrder.Status.PAID,
        payment_completed_at__isnull=False, consulting_date__isnull=False,
        consulting_time__isnull=False,
        sms_status__in=(S.FAILED, S.DISABLED) if retry else (S.PENDING,),
    ).exclude(customer_phone="").exclude(payment_key__isnull=True).exclude(payment_key="")
    if not settings.SOLAPI_SMS_ENABLED:
        eligible.update(sms_status=S.DISABLED, sms_error="SMS disabled; no request sent.")
        return False
    if not eligible.update(sms_status=S.SENDING, sms_error="", sms_status_code="", sms_message_id="",
                           sms_requested_at=timezone.now(), sms_attempts=F("sms_attempts") + 1,
                           sms_accepted_at=None, sms_sent_at=None):
        return False
    order.refresh_from_db()
    target = PaymentOrder.objects.filter(pk=order.pk, sms_status=S.SENDING)
    try:
        phone = normalize_phone(order.customer_phone)
        sender = normalize_phone(settings.SOLAPI_SENDER_NUMBER, sender=True)
        if not settings.SOLAPI_API_KEY or not settings.SOLAPI_API_SECRET:
            raise ValueError("SolAPI credentials are not configured.")
    except ValueError as error:
        target.update(sms_status=S.FAILED, sms_error=str(error))
        return False
    try:
        result = _api("/send-many/detail", {"messages": [{"to": phone, "from": sender,
                      "text": reservation_message(order), "subject": "GSO 문의하기 완료!", "type": "LMS"}], "allowDuplicates": False})
        entries = result.get("messageList", [])
        failures = result.get("failedMessageList", [])
        if len(entries) == 1 and entries[0].get("messageId") and str(entries[0].get("statusCode")) == "2000":
            target.update(sms_status=S.ACCEPTED, sms_message_id=entries[0]["messageId"],
                          sms_status_code="2000", sms_accepted_at=timezone.now())
            return True
        if not entries and len(failures) == 1 and re.fullmatch(r"[35]\d{3}", str(failures[0].get("statusCode", ""))):
            target.update(sms_status=S.FAILED, sms_error="SolAPI rejected message registration.",
                          sms_status_code=str(failures[0]["statusCode"]))
            return False
    except HTTPError as error:
        # Only explicit client rejection is safe to retry. Never store response bodies.
        state = S.FAILED if error.code in (400, 401, 403, 404, 429) else S.UNKNOWN
        target.update(sms_status=state, sms_error=_safe_http_error(error))
        return False
    except (URLError, TimeoutError, OSError, HTTPException, ValueError, TypeError, AttributeError, KeyError):
        pass
    target.update(sms_status=S.UNKNOWN, sms_error="Request outcome unknown; verify in SolAPI console before any resend.")
    return False


def sync_sms_status(order):
    """Read-only provider lookup; never sends a message."""
    S = PaymentOrder.SMSStatus
    order.refresh_from_db()
    if not settings.SOLAPI_SMS_ENABLED or order.sms_status != S.ACCEPTED or not order.sms_message_id:
        return False
    target = PaymentOrder.objects.filter(pk=order.pk, sms_status=S.ACCEPTED, sms_message_id=order.sms_message_id)
    try:
        result = _api("/list?" + urlencode({"criteria": "messageId", "cond": "eq", "value": order.sms_message_id}))
        entry = result["messageList"][order.sms_message_id]
        code = str(entry["statusCode"])
        if entry.get("status") == "COMPLETE" and code == "4000":
            target.update(sms_status=S.SENT, sms_status_code=code, sms_error="", sms_sent_at=timezone.now())
        elif entry.get("status") == "COMPLETE" and re.fullmatch(r"[35]\d{3}", code):
            target.update(sms_status=S.FAILED, sms_status_code=code, sms_error="SolAPI reported delivery failure.")
        else:
            return False
        return True
    except HTTPError as error:
        target.update(sms_error=_safe_http_error(error))
        return False
    except (URLError, OSError, HTTPException, ValueError, KeyError, TypeError, AttributeError):
        target.update(sms_error="SolAPI status lookup failed; delivery status preserved.")
        return False
