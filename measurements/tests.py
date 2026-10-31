import json
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from greenhouses.models import Greenhouse
from measurements.models import Measurement
from measurements.services import parse_timestamp, validate_csv_frame, validate_measurement_values
from sensors.models import Sensor


class MeasurementValidationTests(TestCase):
    def setUp(self):
        self.greenhouse = Greenhouse.objects.create(name="테스트", length_m=10, width_m=5, height_m=3)
        self.sensor = Sensor.objects.create(greenhouse=self.greenhouse, external_id="TEST-1", name="테스트 센서", x=2, y=2.5, z=1.5)

    def confirm_staged(self, response, follow=False):
        """Confirm the positions shown to the user; uploads no longer save immediately."""
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        data = {name: field.initial for name, field in form.fields.items() if name != "confirm"}
        data.update(greenhouse_id=self.greenhouse.pk, stage="confirm", token=response.context["token"], confirm="on")
        return self.client.post("/analysis/upload/", data, follow=follow)

    def test_rejects_measurements_outside_greenhouse_dimensions(self):
        values = {"temperature": 20, "humidity": 60, "x": 11, "y": 2, "z": 1}
        with self.assertRaisesMessage(ValueError, "x는 온실 길이"):
            validate_measurement_values(values, self.greenhouse, self.sensor)

    def test_naive_measurement_time_uses_configured_local_timezone(self):
        stamp = parse_timestamp("2026-10-14T10:30:00")
        self.assertEqual(stamp.utcoffset(), timezone.get_current_timezone().utcoffset(stamp.replace(tzinfo=None)))

    def test_csv_validation_accepts_standard_schema(self):
        import pandas as pd

        frame = pd.DataFrame([{
            "timestamp": "2026-10-14T10:30:00+09:00",
            "greenhouse_id": self.greenhouse.pk,
            "sensor_id": self.sensor.external_id,
            "temperature": 21.5,
            "humidity": 63,
            "x": 2,
            "y": 2.5,
            "z": 1.5,
        }])
        records = validate_csv_frame(frame, self.greenhouse)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].source, Measurement.Source.CSV)

    def test_analysis_and_uploaded_csv_pages_work(self):
        response = self.client.get("/analysis/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SAMPLE DATA")
        csv_bytes = (
            "timestamp,greenhouse_id,sensor_id,temperature,humidity,x,y,z\n"
            f"2026-10-14T10:30:00+09:00,{self.greenhouse.pk},{self.sensor.external_id},21.5,63,2,2.5,1.5\n"
        ).encode("utf-8")
        upload = SimpleUploadedFile("readings.csv", csv_bytes, content_type="text/csv")
        result = self.client.post("/analysis/upload/", {"greenhouse_id": self.greenhouse.pk, "file": upload})
        self.assertEqual(Measurement.objects.count(), 0)
        result = self.confirm_staged(result)
        self.assertEqual(result.status_code, 302)
        measurement = Measurement.objects.get(sensor=self.sensor)
        self.assertEqual(measurement.source, Measurement.Source.CSV)

    def korean_csv(self, rows):
        return "측정일시,온실ID,센서ID,온도(°C),습도(%),X좌표(m),Y좌표(m),Z좌표(m)\n" + rows

    def test_korean_upload_saves_registered_sensors_and_updates_both_charts(self):
        from unittest.mock import patch
        import plotly.graph_objects as go

        rows = []
        for index in range(1, 4):
            Sensor.objects.create(greenhouse=self.greenhouse, external_id=f"S{index:02}", name=f"센서 {index}", x=index, y=2, z=1.5)
            rows.append(f"2025-01-01 10:00:00,Null,S{index:02},{20 + index},{60 + index},Null,Null,Null")
        for encoding in ("utf-8-sig", "cp949"):
            with self.subTest(encoding=encoding):
                Measurement.objects.all().delete()
                upload = SimpleUploadedFile("센서온습도_.csv", self.korean_csv("\n".join(rows)).encode(encoding))
                figures = []
                def capture(figure, **kwargs):
                    figures.append(figure.to_plotly_json())
                    return "<div>chart</div>"
                staged = self.client.post("/analysis/upload/", {"greenhouse_id": self.greenhouse.pk, "file": upload})
                saved = self.confirm_staged(staged, follow=True)
                self.assertContains(saved, "CSV 3건을 저장했습니다")
                with patch.object(go.Figure, "to_html", capture):
                    response = self.client.get(f"/analysis/?greenhouse={self.greenhouse.pk}&period=all")
                self.assertEqual(Measurement.objects.count(), 3)
                self.assertFalse(response.context["is_demo"])
                self.assertEqual(response.context["period"], "all")
                self.assertContains(response, 'id="csv-upload"')
                for measurement in Measurement.objects.all():
                    self.assertEqual(measurement.x, float(measurement.sensor.x))
                    self.assertEqual(measurement.greenhouse_id, self.greenhouse.pk)
                    self.assertEqual(measurement.source, Measurement.Source.CSV)
                self.assertEqual(len(figures), 2)
                for figure in figures:
                    self.assertEqual(len(figure["data"]), 3)
                self.assertEqual(response.context["stats"]["temperature"]["mean"], 22)
                self.assertEqual(response.context["stats"]["humidity"]["mean"], 62)

    def test_csv_invalid_row_rolls_back_entire_file(self):
        for invalid in (
            "2026-01-01 10:01:00,Null,Null,21,60,Null,Null,Null",
            f"2026-01-01 10:01:00,{self.greenhouse.pk + 1},TEST-1,21,60,Null,Null,Null",
            "2026-01-01 10:01:00,Null,TEST-1,21,60,11,Null,Null",
            "2026-01-01 10:01:00,Null,TEST-1,21,101,Null,Null,Null",
        ):
            with self.subTest(row=invalid):
                rows = "2026-01-01 10:00:00,Null,TEST-1,21,60,Null,Null,Null\n" + invalid
                upload = SimpleUploadedFile("invalid.csv", self.korean_csv(rows).encode("utf-8"))
                response = self.client.post("/analysis/upload/", {"greenhouse_id": self.greenhouse.pk, "file": upload}, follow=True)
                self.assertEqual(Measurement.objects.count(), 0)
                self.assertContains(response, "이번 파일은 저장되지 않았습니다: 3행")

    def test_csv_rejects_multiple_installation_positions_in_one_file(self):
        rows = (
            "2026-01-01 10:00:00,Null,TEST-1,21,60,Null,3,Null\n"
            f"2026-01-01 10:01:00,{self.greenhouse.pk},TEST-1,22,61,4,Null,2"
        )
        upload = SimpleUploadedFile("mixed.csv", self.korean_csv(rows).encode("utf-8"))
        response = self.client.post("/analysis/upload/", {"greenhouse_id": self.greenhouse.pk, "file": upload}, follow=True)
        self.assertContains(response, "한 파일에 여러 설치 위치")
        self.assertEqual(Measurement.objects.count(), 0)

    def test_identical_duplicate_csv_rows_are_saved_once_after_confirmation(self):
        row = "2026-01-01 10:00:00,Null,TEST-1,21,60,Null,Null,Null"
        upload = SimpleUploadedFile("duplicate.csv", self.korean_csv(row + "\n" + row).encode("utf-8"))
        response = self.client.post("/analysis/upload/", {"greenhouse_id": self.greenhouse.pk, "file": upload})
        self.assertEqual(Measurement.objects.count(), 0)
        self.confirm_staged(response)
        self.assertEqual(Measurement.objects.count(), 1)


@override_settings(MEASUREMENT_INGEST_TOKEN="test-token")
class IngestApiTests(TestCase):
    def setUp(self):
        self.greenhouse = Greenhouse.objects.create(name="API 테스트", length_m=10, width_m=5, height_m=3)
        self.sensor = Sensor.objects.create(greenhouse=self.greenhouse, external_id="API-1", name="API 센서", x=2, y=2, z=1.5)
        self.payload = {
            "timestamp": timezone.now().isoformat(),
            "greenhouse_id": self.greenhouse.pk,
            "sensor_id": self.sensor.external_id,
            "temperature": 22.5, "humidity": 65.2, "x": 2, "y": 2, "z": 1.5,
        }

    def test_ingest_persists_measurement_and_deduplicates_same_sensor_timestamp(self):
        first = self.client.post(
            "/api/v1/measurements/ingest/",
            data=json.dumps(self.payload),
            content_type="application/json",
            HTTP_X_API_KEY="test-token",
        )
        again = self.client.post(
            "/api/v1/measurements/ingest/",
            data=json.dumps(self.payload),
            content_type="application/json",
            HTTP_X_API_KEY="test-token",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["created"], 1)
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.json()["duplicates"], 1)
        self.assertEqual(Measurement.objects.filter(source=Measurement.Source.API).count(), 1)

    def test_ingest_requires_token_and_valid_data(self):
        unauthorized = self.client.post("/api/v1/measurements/ingest/", data=json.dumps(self.payload), content_type="application/json")
        self.assertEqual(unauthorized.status_code, 401)
        invalid_payload = {**self.payload, "humidity": 101}
        invalid = self.client.post(
            "/api/v1/measurements/ingest/",
            data=json.dumps(invalid_payload),
            content_type="application/json",
            HTTP_X_API_KEY="test-token",
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(Measurement.objects.count(), 0)
