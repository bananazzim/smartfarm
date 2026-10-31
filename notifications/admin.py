from django.contrib import admin

from .models import AlertEvent, AlertSetting


@admin.register(AlertSetting)
class AlertSettingAdmin(admin.ModelAdmin):
    list_display = ("greenhouse", "phone", "temperature_min", "temperature_max", "humidity_min", "humidity_max")


@admin.register(AlertEvent)
class AlertEventAdmin(admin.ModelAdmin):
    list_display = ("greenhouse", "status", "created_at")
    readonly_fields = ("created_at",)
