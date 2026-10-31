from django.contrib import admin, messages

from .models import PaymentOrder
from .sheets import send_paid_order_to_sheets


@admin.register(PaymentOrder)
class PaymentOrderAdmin(admin.ModelAdmin):
    actions = ("retry_google_sheets_delivery",)
    list_display = (
        "order_number",
        "product_name",
        "amount",
        "status",
        "sheets_delivery_status",
        "sms_status",
        "payment_key",
        "created_at",
        "payment_completed_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("order_number", "product_name", "payment_key")
    readonly_fields = (
        "sms_status", "sms_error", "sms_message_id", "sms_status_code",
        "sms_attempts", "sms_requested_at", "sms_accepted_at", "sms_sent_at",
        "order_number",
        "product_name",
        "amount",
        "status",
        "payment_key",
        "created_at",
        "payment_completed_at",
        "discovery_source",
        "consulting_interest",
        "investment_budget",
        "annual_revenue",
        "annual_profit",
        "customer_name",
        "customer_phone",
        "consulting_date",
        "consulting_time",
        "greenhouse_location",
        "consulting_request",
        "privacy_consent",
        "sheets_delivery_status",
        "sheets_delivery_error",
        "sheets_sent_at",
    )

    @admin.action(description="선택한 결제완료 주문의 Google Sheets 전송 재시도")
    def retry_google_sheets_delivery(self, request, queryset):
        sent_count = 0
        retry_orders = queryset.filter(
            status=PaymentOrder.Status.PAID,
            sheets_delivery_status=PaymentOrder.SheetsDeliveryStatus.FAILED,
        )
        attempted_count = retry_orders.count()
        for order in retry_orders:
            if send_paid_order_to_sheets(order):
                sent_count += 1
        failed_count = attempted_count - sent_count
        if not attempted_count:
            self.message_user(
                request,
                "재시도할 결제완료 Google Sheets 전송이 없습니다.",
                level=messages.WARNING,
            )
            return
        self.message_user(
            request,
            f"{sent_count}건 전송 완료, {failed_count}건 전송 실패. 실패 건은 주문의 오류 기록을 확인해 주세요.",
            level=messages.SUCCESS if not failed_count else messages.WARNING,
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
