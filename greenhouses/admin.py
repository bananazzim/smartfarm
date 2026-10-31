from django.contrib import admin

from .models import Greenhouse


@admin.register(Greenhouse)
class GreenhouseAdmin(admin.ModelAdmin):
    list_display = ("name", "shape", "length_m", "width_m", "height_m", "sensor_count", "created_at")
    search_fields = ("name", "crop")
