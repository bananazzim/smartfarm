from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from greenhouses.models import Greenhouse
from measurements.demo import dashboard_series
from measurements.models import Measurement
from notifications.models import AlertSetting
from sensors.models import Sensor


class Command(BaseCommand):
    help = "Create or refresh a reproducible sample greenhouse and measurement dataset."

    @transaction.atomic
    def handle(self, *args, **options):
        greenhouse, _ = Greenhouse.objects.get_or_create(
            name="한빛 테스트 온실",
            defaults={
                "shape": Greenhouse.Shape.SINGLE,
                "length_m": 30,
                "width_m": 8,
                "height_m": 4,
                "ventilation": "측창 + 천창",
                "crop": "상추",
                "sensor_count": 3,
            },
        )
        ratios = (0.2, 0.5, 0.8)
        sensors = []
        for index in range(min(max(greenhouse.sensor_count, 1), 3)):
            sensor, _ = Sensor.objects.update_or_create(
                greenhouse=greenhouse,
                external_id=f"DEMO-{greenhouse.pk}-{index + 1}",
                defaults={
                    "name": f"센서 {chr(65 + index)}",
                    "x": round(float(greenhouse.length_m) * ratios[index], 3),
                    "y": round(float(greenhouse.width_m) / 2, 3),
                    "z": min(1.5, float(greenhouse.height_m) * 0.75),
                    "status": Sensor.Status.DEMO,
                },
            )
            sensors.append(sensor)
        series = dashboard_series()
        created = 0
        for time_index, stamp in enumerate(series["timestamps"]):
            for sensor_index, sensor in enumerate(sensors):
                temp_offset = (-0.3, 0.1, 0.4)[sensor_index]
                humidity_offset = (1.6, -0.5, -1.2)[sensor_index]
                _, was_created = Measurement.objects.update_or_create(
                    sensor=sensor,
                    timestamp=stamp,
                    defaults={
                        "greenhouse": greenhouse,
                        "temperature": round(series["temperature"][time_index] + temp_offset, 2),
                        "humidity": round(series["humidity"][time_index] + humidity_offset, 2),
                        "x": float(sensor.x),
                        "y": float(sensor.y),
                        "z": float(sensor.z),
                        "source": Measurement.Source.DEMO,
                    },
                )
                created += int(was_created)
        AlertSetting.objects.get_or_create(greenhouse=greenhouse)
        self.stdout.write(self.style.SUCCESS(
            f"DEMO greenhouse ready: {greenhouse.name} (id={greenhouse.pk}), "
            f"{len(sensors)} sample sensors, {created} new sample measurements. "
            f"Dataset timestamps use {timezone.get_current_timezone_name()}."
        ))
