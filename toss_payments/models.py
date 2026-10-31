from django.db import models


class PaymentOrder(models.Model):
    class SMSStatus(models.TextChoices):
        PENDING = "pending", "미발송"
        DISABLED = "disabled", "테스트 모드 (미발송)"
        SENDING = "sending", "요청 중 (재발송 금지)"
        ACCEPTED = "accepted", "접수 완료"
        SENT = "sent", "발송 완료"
        FAILED = "failed", "실패 (재시도 가능)"
        UNKNOWN = "unknown", "결과 불명 (재발송 금지)"

    sms_status = models.CharField(max_length=10, choices=SMSStatus.choices, default=SMSStatus.PENDING)
    sms_error = models.TextField(blank=True)
    sms_message_id = models.CharField(max_length=100, blank=True)
    sms_status_code = models.CharField(max_length=10, blank=True)
    sms_attempts = models.PositiveIntegerField(default=0)
    sms_requested_at = models.DateTimeField(null=True, blank=True)
    sms_accepted_at = models.DateTimeField(null=True, blank=True)
    sms_sent_at = models.DateTimeField(null=True, blank=True)

    class Status(models.TextChoices):
        PENDING = "pending", "결제 대기"
        PROCESSING = "processing", "승인 확인 중"
        PAID = "paid", "결제 완료"
        FAILED = "failed", "결제 실패"

    class SheetsDeliveryStatus(models.TextChoices):
        PENDING = "pending", "전송 대기"
        SENDING = "sending", "전송 중"
        SENT = "sent", "전송 완료"
        FAILED = "failed", "전송 실패"

    order_number = models.CharField("주문번호", max_length=40, unique=True)
    product_name = models.CharField("상품명", max_length=100)
    amount = models.PositiveIntegerField("결제 금액")
    status = models.CharField(
        "결제 상태",
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )
    payment_key = models.CharField(
        "토스 결제 키",
        max_length=200,
        unique=True,
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField("생성일", auto_now_add=True)
    payment_completed_at = models.DateTimeField("결제 완료일", blank=True, null=True)
    discovery_source = models.CharField("GSO 유입 경로", max_length=32, blank=True)
    consulting_interest = models.CharField("상담 관심 분야", max_length=32, blank=True)
    investment_budget = models.CharField("예상 투자 예산", max_length=32, blank=True)
    annual_revenue = models.CharField("연매출", max_length=32, blank=True)
    annual_profit = models.CharField("연간 순수익", max_length=32, blank=True)
    customer_name = models.CharField("고객명", max_length=50, blank=True)
    customer_phone = models.CharField("전화번호", max_length=13, blank=True)
    consulting_date = models.DateField("희망 상담 날짜", blank=True, null=True)
    consulting_time = models.TimeField("희망 상담 시간", blank=True, null=True)
    greenhouse_location = models.CharField("온실 위치", max_length=200, blank=True)
    consulting_request = models.TextField("요청사항", blank=True)
    privacy_consent = models.BooleanField("개인정보 수집 및 이용 동의", default=False)
    sheets_delivery_status = models.CharField(
        "Google Sheets 전송 상태",
        max_length=8,
        choices=SheetsDeliveryStatus.choices,
        default=SheetsDeliveryStatus.PENDING,
    )
    sheets_delivery_error = models.TextField("Google Sheets 전송 오류", blank=True)
    sheets_sent_at = models.DateTimeField("Google Sheets 전송 완료일", blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "결제 주문"
        verbose_name_plural = "결제 주문"

    def __str__(self):
        return f"{self.order_number} - {self.product_name}"
