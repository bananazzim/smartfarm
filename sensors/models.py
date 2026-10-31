from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class Sensor(models.Model):
    class Status(models.TextChoices):
        DEMO = "demo", "데모"
        ACTIVE = "active", "연결됨"
        INACTIVE = "inactive", "미연결"

    greenhouse = models.ForeignKey("greenhouses.Greenhouse", on_delete=models.CASCADE, related_name="sensors", verbose_name="온실")
    external_id = models.CharField("센서 ID", max_length=80)
    name = models.CharField("표시명", max_length=80)
    x = models.DecimalField("x (길이 방향, m)", max_digits=8, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(0)])
    y = models.DecimalField("y (폭 방향, m)", max_digits=8, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(0)])
    z = models.DecimalField("z (바닥 기준, m)", max_digits=8, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(0)])
    status = models.CharField("상태", max_length=10, choices=Status.choices, default=Status.DEMO)
    created_at = models.DateTimeField("등록일", auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["greenhouse", "external_id"], name="unique_sensor_greenhouse_external_id")]
        ordering = ["name"]
        verbose_name = "센서"
        verbose_name_plural = "센서"

    def clean(self):
        super().clean()
        if not self.greenhouse_id:
            return
        greenhouse = self.greenhouse
        for field, bound in (("x", greenhouse.length_m), ("y", greenhouse.width_m), ("z", greenhouse.height_m)):
            value = getattr(self, field)
            if value is not None and value > float(bound):
                raise ValidationError({field: "센서 좌표가 온실 크기를 벗어났습니다."})
        if all(getattr(self, axis) is not None for axis in "xyz"):
            from .geometry import validate_position
            try:
                validate_position(greenhouse, [getattr(self, axis) for axis in "xyz"])
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc

    def __str__(self):
        return f"{self.name} ({self.external_id})"
