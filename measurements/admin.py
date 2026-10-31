from django.contrib import admin

from .models import Measurement


@admin.register(Measurement)
class MeasurementAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "greenhouse", "sensor", "temperature", "humidity", "source")
    list_filter = ("source", "greenhouse")
    search_fields = ("sensor__external_id", "sensor__name")
    date_hierarchy = "timestamp"
