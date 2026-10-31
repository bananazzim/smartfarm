from django.apps import AppConfig


class MeasurementsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "measurements"
    verbose_name = "환경 측정 데이터"
