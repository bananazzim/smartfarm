from django.contrib import admin

from .models import Sensor


@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):
    list_display = ("name", "external_id", "greenhouse", "x", "y", "z", "status")
    list_filter = ("status", "greenhouse")
    search_fields = ("name", "external_id")
