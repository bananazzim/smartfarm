from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Measurement(models.Model):
    class Source(models.TextChoices):
        DEMO = "demo", "샘플 데이터"
        CSV = "csv", "CSV 업로드"
        API = "api", "수신 API"

    timestamp = models.DateTimeField("측정 시각", db_index=True)
    greenhouse = models.ForeignKey("greenhouses.Greenhouse", on_delete=models.CASCADE, related_name="measurements", verbose_name="온실")
    sensor = models.ForeignKey("sensors.Sensor", on_delete=models.CASCADE, related_name="measurements", verbose_name="센서")
    temperature = models.FloatField("온도 (°C)", validators=[MinValueValidator(-50), MaxValueValidator(80)])
    humidity = models.FloatField("상대습도 (%)", validators=[MinValueValidator(0), MaxValueValidator(100)])
    x = models.FloatField("x (m)", validators=[MinValueValidator(0)])
    y = models.FloatField("y (m)", validators=[MinValueValidator(0)])
    z = models.FloatField("z (m)", validators=[MinValueValidator(0)])
    source = models.CharField("데이터 출처", max_length=8, choices=Source.choices, default=Source.DEMO)
    received_at = models.DateTimeField("수신 시각", auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        constraints = [
            models.UniqueConstraint(fields=["sensor", "timestamp"], name="unique_measurement_sensor_timestamp"),
        ]
        verbose_name = "측정 데이터"
        verbose_name_plural = "측정 데이터"

    def clean(self):
        super().clean()
        if self.sensor_id and self.greenhouse_id and self.sensor.greenhouse_id != self.greenhouse_id:
            raise ValidationError({"sensor": "선택한 센서는 해당 온실에 등록되어 있지 않습니다."})
        if self.greenhouse_id and self.x is not None and self.x > float(self.greenhouse.length_m):
            raise ValidationError({"x": "x 좌표가 온실 길이를 초과합니다."})
        if self.greenhouse_id and self.y is not None and self.y > float(self.greenhouse.width_m):
            raise ValidationError({"y": "y 좌표가 온실 폭을 초과합니다."})
        if self.greenhouse_id and self.z is not None and self.z > float(self.greenhouse.height_m):
            raise ValidationError({"z": "z 좌표가 온실 높이를 초과합니다."})

    def __str__(self):
        return f"{self.sensor} · {self.timestamp:%Y-%m-%d %H:%M}"
