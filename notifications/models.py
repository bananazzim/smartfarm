from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models


class AlertSetting(models.Model):
    greenhouse = models.OneToOneField("greenhouses.Greenhouse", on_delete=models.CASCADE, related_name="alert_setting", verbose_name="온실")
    phone = models.CharField("연락처", max_length=30, blank=True, validators=[RegexValidator(r"^\+?[0-9][0-9 -]{7,19}$", "숫자, 공백, 하이픈으로 연락처를 입력해 주세요.")])
    temperature_min = models.FloatField("최저 온도 (°C)", default=10, validators=[MinValueValidator(-50), MaxValueValidator(80)])
    temperature_max = models.FloatField("최고 온도 (°C)", default=30, validators=[MinValueValidator(-50), MaxValueValidator(80)])
    humidity_min = models.FloatField("최저 습도 (%)", default=40, validators=[MinValueValidator(0), MaxValueValidator(100)])
    humidity_max = models.FloatField("최고 습도 (%)", default=85, validators=[MinValueValidator(0), MaxValueValidator(100)])
    updated_at = models.DateTimeField("수정일", auto_now=True)

    class Meta:
        verbose_name = "알림 설정"
        verbose_name_plural = "알림 설정"

    def clean(self):
        from django.core.exceptions import ValidationError

        super().clean()
        if self.temperature_min >= self.temperature_max:
            raise ValidationError({"temperature_max": "최고 온도는 최저 온도보다 높아야 합니다."})
        if self.humidity_min >= self.humidity_max:
            raise ValidationError({"humidity_max": "최고 습도는 최저 습도보다 높아야 합니다."})


class AlertEvent(models.Model):
    greenhouse = models.ForeignKey("greenhouses.Greenhouse", on_delete=models.CASCADE, related_name="alerts", verbose_name="온실")
    message = models.CharField("메시지", max_length=300)
    status = models.CharField("전송 상태", max_length=20, default="mock_sent")
    created_at = models.DateTimeField("발생 시각", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "알림 이력"
        verbose_name_plural = "알림 이력"
