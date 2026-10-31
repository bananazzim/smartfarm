import base64
import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .forms import ReservationForm, SurveyForm
from .models import PaymentOrder
from .sheets import send_paid_order_to_sheets
from .sms import send_paid_order_sms

logger = logging.getLogger(__name__)

PRODUCT_NAME = "GSO 컨설팅"
PRODUCT_AMOUNT = 30_000
CONFIRM_URL = "https://api.tosspayments.com/v1/payments/confirm"


def _payment_keys_configured() -> bool:
    return bool(settings.TOSS_CLIENT_KEY and settings.TOSS_SECRET_KEY)


def _checkout_context(request: HttpRequest, order: PaymentOrder | None = None) -> dict:
    context = {
        "order": order,
        "can_checkout": _payment_keys_configured(),
        "client_key": settings.TOSS_CLIENT_KEY,
        "success_url": request.build_absolute_uri(reverse("toss_payments:payment_success")),
        "fail_url": request.build_absolute_uri(reverse("toss_payments:payment_fail")),
    }
    if order is not None and context["can_checkout"]:
        context["payment_config"] = {
            "orderNumber": order.order_number,
            "productName": order.product_name,
            "amount": order.amount,
            "clientKey": settings.TOSS_CLIENT_KEY,
            "successUrl": context["success_url"],
            "failUrl": context["fail_url"],
            "reservationUrl": reverse(
                "toss_payments:save_reservation",
                kwargs={"order_number": order.order_number},
            ),
        }
    return context


def _render_failure(
    request: HttpRequest,
    message: str,
    order: PaymentOrder | None = None,
    status: int = 400,
) -> HttpResponse:
    return render(
        request,
        "toss_payments/fail.html",
        {"order": order, "message": message},
        status=status,
    )


@require_GET
def checkout_start(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "toss_payments/checkout.html",
        _checkout_context(request),
    )


@require_POST
def create_order(request: HttpRequest) -> HttpResponse:
    if not _payment_keys_configured():
        return render(
            request,
            "toss_payments/checkout.html",
            _checkout_context(request),
            status=503,
        )

    survey_form = SurveyForm(request.POST)
    if not survey_form.is_valid():
        context = _checkout_context(request)
        context["survey_error"] = "필수 사전 설문 항목을 확인해 주세요."
        return render(request, "toss_payments/checkout.html", context, status=400)

    order = PaymentOrder.objects.create(
        order_number=f"GSO-{uuid4().hex}",
        product_name=PRODUCT_NAME,
        amount=PRODUCT_AMOUNT,
        **survey_form.cleaned_data,
    )
    return redirect("toss_payments:checkout_order", order_number=order.order_number)


@require_POST
def save_reservation(request: HttpRequest, order_number: str) -> JsonResponse:
    order = get_object_or_404(PaymentOrder, order_number=order_number)
    if order.status != PaymentOrder.Status.PENDING:
        return JsonResponse(
            {"ok": False, "error": "이 주문에는 예약 정보를 저장할 수 없습니다."},
            status=409,
        )

    reservation_form = ReservationForm(request.POST)
    if not reservation_form.is_valid():
        error = (
            "개인정보 수집 및 이용에 동의해야 예약 정보를 저장할 수 있습니다."
            if "privacy_consent" in reservation_form.errors
            else "예약 정보를 확인해 주세요. 상담 일시는 현재 시각보다 이후여야 합니다."
        )
        return JsonResponse({"ok": False, "error": error}, status=400)

    updated = PaymentOrder.objects.filter(
        pk=order.pk,
        status=PaymentOrder.Status.PENDING,
    ).update(**reservation_form.cleaned_data)
    if not updated:
        return JsonResponse(
            {"ok": False, "error": "이 주문에는 예약 정보를 저장할 수 없습니다."},
            status=409,
        )
    return JsonResponse({"ok": True})


@require_GET
def checkout_order(request: HttpRequest, order_number: str) -> HttpResponse:
    order = get_object_or_404(PaymentOrder, order_number=order_number)
    if order.status != PaymentOrder.Status.PENDING:
        return _render_failure(
            request,
            "이 주문은 새 결제를 시작할 수 없습니다. 결제 상태를 확인해 주세요.",
            order,
            status=409,
        )
    return render(
        request,
        "toss_payments/checkout.html",
        _checkout_context(request, order),
    )


def _confirm_payment(payment_key: str, order_number: str, amount: int) -> dict:
    authorization = base64.b64encode(
        f"{settings.TOSS_SECRET_KEY}:".encode("utf-8")
    ).decode("ascii")
    body = json.dumps(
        {
            "paymentKey": payment_key,
            "orderId": order_number,
            "amount": amount,
        }
    ).encode("utf-8")
    api_request = Request(
        CONFIRM_URL,
        data=body,
        headers={
            "Authorization": f"Basic {authorization}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(api_request, timeout=10) as response:
        return json.loads(response.read())


@require_GET
def payment_success(request: HttpRequest) -> HttpResponse:
    payment_key = request.GET.get("paymentKey", "")
    order_number = request.GET.get("orderId", "")
    amount_text = request.GET.get("amount", "")
    if (
        not payment_key
        or len(payment_key) > 200
        or not order_number
        or len(order_number) > 40
        or len(amount_text) > 10
        or not amount_text.isascii()
        or not amount_text.isdigit()
    ):
        return _render_failure(request, "결제 승인 정보가 올바르지 않습니다.")

    order = PaymentOrder.objects.filter(order_number=order_number).first()
    if order is None:
        return _render_failure(request, "주문 정보를 찾을 수 없습니다.")
    if int(amount_text) != order.amount:
        logger.warning("Payment amount mismatch for order %s", order_number)
        return _render_failure(request, "주문 금액이 일치하지 않습니다.", order)
    if (
        not order.privacy_consent
        or not order.customer_name
        or not order.customer_phone
        or order.consulting_date is None
        or order.consulting_time is None
    ):
        return _render_failure(
            request,
            "예약 정보와 개인정보 동의가 확인되지 않아 결제를 승인할 수 없습니다.",
            order,
            status=409,
        )
    if not settings.TOSS_SECRET_KEY:
        return _render_failure(
            request,
            "토스페이먼츠 비밀 키가 설정되지 않아 결제를 승인할 수 없습니다.",
            order,
            status=503,
        )

    try:
        with transaction.atomic():
            order = PaymentOrder.objects.select_for_update().get(pk=order.pk)
            if order.status == PaymentOrder.Status.PAID:
                if order.payment_key == payment_key:
                    return render(request, "toss_payments/success.html", {"order": order})
                return _render_failure(request, "이미 처리된 주문입니다.", order, status=409)
            if order.status != PaymentOrder.Status.PENDING:
                return _render_failure(
                    request,
                    "이 주문은 이미 승인 처리 중이거나 결제할 수 없는 상태입니다.",
                    order,
                    status=409,
                )
            order.status = PaymentOrder.Status.PROCESSING
            order.payment_key = payment_key
            order.save(update_fields=("status", "payment_key"))
    except IntegrityError:
        logger.warning("Payment key was already used for order %s", order_number)
        return _render_failure(request, "이미 사용된 결제 정보입니다.", order, status=409)

    try:
        confirmation = _confirm_payment(payment_key, order_number, order.amount)
    except HTTPError as error:
        logger.warning(
            "Toss payment confirmation rejected for order %s (HTTP %s)",
            order_number,
            error.code,
        )
        if 400 <= error.code < 500 and error.code != 408:
            PaymentOrder.objects.filter(
                pk=order.pk,
                status=PaymentOrder.Status.PROCESSING,
                payment_key=payment_key,
            ).update(status=PaymentOrder.Status.FAILED)
            order.refresh_from_db()
            return _render_failure(request, "토스페이먼츠 결제 승인이 거절되었습니다.", order)
        return _render_failure(
            request,
            "결제 승인 결과를 확인할 수 없습니다. 중복 승인을 막기 위해 주문을 승인 확인 중으로 유지합니다.",
            order,
            status=503,
        )
    except (URLError, TimeoutError, OSError, json.JSONDecodeError):
        logger.exception("Toss payment confirmation could not be verified for order %s", order_number)
        return _render_failure(
            request,
            "결제 승인 결과를 확인할 수 없습니다. 중복 승인을 막기 위해 주문을 승인 확인 중으로 유지합니다.",
            order,
            status=503,
        )

    if (
        not isinstance(confirmation, dict)
        or confirmation.get("paymentKey") != payment_key
        or confirmation.get("orderId") != order_number
        or confirmation.get("totalAmount") != order.amount
        or confirmation.get("status") != "DONE"
    ):
        logger.error("Toss confirmation response did not match order %s", order_number)
        PaymentOrder.objects.filter(
            pk=order.pk,
            status=PaymentOrder.Status.PROCESSING,
            payment_key=payment_key,
        ).update(status=PaymentOrder.Status.FAILED)
        order.refresh_from_db()
        return _render_failure(request, "토스페이먼츠 승인 응답을 검증할 수 없습니다.", order)

    updated = PaymentOrder.objects.filter(
        pk=order.pk,
        status=PaymentOrder.Status.PROCESSING,
        payment_key=payment_key,
    ).update(
        status=PaymentOrder.Status.PAID,
        payment_completed_at=timezone.now(),
    )
    if not updated:
        order.refresh_from_db()
        if order.status == PaymentOrder.Status.PAID and order.payment_key == payment_key:
            return render(request, "toss_payments/success.html", {"order": order})
        return _render_failure(request, "결제 완료 상태를 저장하지 못했습니다.", order, status=409)

    order.refresh_from_db()
    # Both run only after the paid transition is committed. Each owns its state.
    def deliver_notifications():
        try:
            send_paid_order_to_sheets(order)
        except Exception:
            logger.error("Unexpected Sheets delivery failure for order %s", order.pk)
        try:
            send_paid_order_sms(order)
        except Exception:
            logger.error("Unexpected SMS delivery failure for order %s", order.pk)

    transaction.on_commit(deliver_notifications)
    return render(request, "toss_payments/success.html", {"order": order})


@require_GET
def payment_fail(request: HttpRequest) -> HttpResponse:
    order_number = request.GET.get("orderId", "")
    order = PaymentOrder.objects.filter(order_number=order_number).first() if order_number else None
    return render(
        request,
        "toss_payments/fail.html",
        {
            "order": order,
            "message": "결제가 완료되지 않았습니다. 결제 상태를 확인한 뒤 다시 시도해 주세요.",
        },
    )
