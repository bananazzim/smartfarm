import json
import logging
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone

from .models import PaymentOrder

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT_SECONDS = 10


def _payload_for_order(order: PaymentOrder) -> dict:
    if order.payment_completed_at is None:
        raise ValueError("Paid order has no payment completion timestamp.")

    return {
        "order_id": order.order_number,
        "paid_at": timezone.localtime(order.payment_completed_at).isoformat(),
        "customer_name": order.customer_name,
        "phone": order.customer_phone,
        "consultation_date": order.consulting_date.isoformat(),
        "consultation_time": order.consulting_time.strftime("%H:%M"),
        "greenhouse_location": order.greenhouse_location,
        "request_notes": order.consulting_request,
        "referral_source": order.discovery_source,
        "interest_area": order.consulting_interest,
        "investment_budget": order.investment_budget,
        "annual_revenue": order.annual_revenue,
        "annual_profit": order.annual_profit,
        "product_name": order.product_name,
        "payment_amount": order.amount,
        "payment_status": "DONE",
        "sms_status": "미발송",
        "secret": settings.GSO_WEBHOOK_SECRET,
    }


def send_paid_order_to_sheets(order: PaymentOrder) -> bool:
    claimed = PaymentOrder.objects.filter(
        pk=order.pk,
        status=PaymentOrder.Status.PAID,
        privacy_consent=True,
        consulting_date__isnull=False,
        consulting_time__isnull=False,
        sheets_delivery_status__in=(
            PaymentOrder.SheetsDeliveryStatus.PENDING,
            PaymentOrder.SheetsDeliveryStatus.FAILED,
        ),
    ).update(
        sheets_delivery_status=PaymentOrder.SheetsDeliveryStatus.SENDING,
        sheets_delivery_error="",
    )
    if not claimed:
        return False

    order.refresh_from_db()
    if not settings.GSO_SHEETS_WEBHOOK_URL or not settings.GSO_WEBHOOK_SECRET:
        _record_failure(order, "GSO Sheets webhook URL or secret is not configured.")
        return False
    try:
        webhook_url = urlsplit(settings.GSO_SHEETS_WEBHOOK_URL)
    except ValueError:
        webhook_url = None
    if (
        webhook_url is None
        or webhook_url.scheme != "https"
        or not webhook_url.netloc
    ):
        _record_failure(order, "GSO Sheets webhook URL must be a valid HTTPS URL.")
        return False

    try:
        body = json.dumps(_payload_for_order(order), ensure_ascii=False).encode("utf-8")
        request = Request(
            webhook_url.geturl(),
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=WEBHOOK_TIMEOUT_SECONDS) as response:
            result = json.loads(response.read(65536))
    except HTTPError as error:
        _record_failure(order, f"Google Apps Script returned HTTP {error.code}.")
        return False
    except (URLError, TimeoutError, OSError):
        _record_failure(order, "Google Apps Script request failed or timed out.")
        return False
    except HTTPException:
        _record_failure(order, "Google Apps Script returned an incomplete response.")
        return False
    except (json.JSONDecodeError, UnicodeDecodeError):
        _record_failure(order, "Google Apps Script returned invalid JSON.")
        return False
    except ValueError:
        _record_failure(order, "Paid order is missing required delivery data.")
        return False

    if not isinstance(result, dict) or result.get("ok") is not True:
        _record_failure(order, "Google Apps Script did not confirm the recorded row.")
        return False

    PaymentOrder.objects.filter(
        pk=order.pk,
        sheets_delivery_status=PaymentOrder.SheetsDeliveryStatus.SENDING,
    ).update(
        sheets_delivery_status=PaymentOrder.SheetsDeliveryStatus.SENT,
        sheets_delivery_error="",
        sheets_sent_at=timezone.now(),
    )
    return True


def _record_failure(order: PaymentOrder, message: str) -> None:
    PaymentOrder.objects.filter(
        pk=order.pk,
        sheets_delivery_status=PaymentOrder.SheetsDeliveryStatus.SENDING,
    ).update(
        sheets_delivery_status=PaymentOrder.SheetsDeliveryStatus.FAILED,
        sheets_delivery_error=message,
    )
    logger.warning("Google Sheets delivery failed for order %s: %s", order.order_number, message)
