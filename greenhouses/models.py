from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class Greenhouse(models.Model):
    class Shape(models.TextChoices):
        SINGLE = "single", "단동"
        CONNECTED = "connected", "연동"

    name = models.CharField("온실명", max_length=100)
    shape = models.CharField("온실 형태", max_length=12, choices=Shape.choices, default=Shape.SINGLE)
    length_m = models.DecimalField("길이(m)", max_digits=7, decimal_places=2, validators=[MinValueValidator(0.1)])
    width_m = models.DecimalField("폭(m)", max_digits=7, decimal_places=2, validators=[MinValueValidator(0.1)])
    height_m = models.DecimalField("높이(m)", max_digits=6, decimal_places=2, validators=[MinValueValidator(0.1)])
    ventilation = models.CharField("환기 방식", max_length=80, default="측창 환기")
    crop = models.CharField("작물", max_length=80, blank=True)
    sensor_count = models.PositiveSmallIntegerField("설치 센서 수", default=3, validators=[MinValueValidator(1)])
    created_at = models.DateTimeField("등록일", auto_now_add=True)
    updated_at = models.DateTimeField("수정일", auto_now=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "온실"
        verbose_name_plural = "온실"

    def clean(self):
        super().clean()
        for field in ("length_m", "width_m", "height_m"):
            value = getattr(self, field)
            if value is not None and value > 500:
                raise ValidationError({field: "500m 이하의 값을 입력해 주세요."})

    def __str__(self):
        return self.name
