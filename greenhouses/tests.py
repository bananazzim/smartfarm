from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from greenhouses.models import Greenhouse


class GreenhouseTests(TestCase):
    def test_greenhouse_size_validation(self):
        greenhouse = Greenhouse(name="invalid", length_m=501, width_m=8, height_m=4)
        with self.assertRaisesMessage(ValidationError, "500m 이하"):
            greenhouse.full_clean()

    def test_create_and_dashboard_pages_render(self):
        greenhouse = Greenhouse.objects.create(name="테스트 온실", length_m=20, width_m=6, height_m=3)
        dashboard = self.client.get(reverse("dashboard"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "SAMPLE DATA")
        self.assertContains(dashboard, 'class="dashboard-hero"')
        self.assertContains(dashboard, "greenhouse-unsplash-eoj6t-cMtNs.jpg")
        self.assertContains(dashboard, "greenhouse-agriculture.jpg")
        self.assertContains(dashboard, "greenhouse-tomatoes.jpg")
        self.assertContains(dashboard, "GREENHOUSE USE CASES")
        self.assertContains(dashboard, "Data Reader")
        self.assertContains(dashboard, "실제 GSO 고객·농가 도입 사례나 실증 성과를 나타내지 않습니다.")
        self.assertNotContains(dashboard, "MAKE SENSE OF YOUR GREENHOUSE")
        rendered_dashboard = dashboard.content.decode()
        gallery_start = rendered_dashboard.index('<section class="gso-use-cases"')
        gallery_end = rendered_dashboard.index('<!-- ==================================================\n     3. GREENHOUSE SNAPSHOT', gallery_start)
        gallery = rendered_dashboard[gallery_start:gallery_end]
        self.assertEqual(gallery.count('class="gso-use-case-card"'), 7)
        self.assertEqual(gallery.count("<a "), 7)
        self.assertEqual(gallery.count("</a>"), 7)
        self.assertIn('data-gallery-total>07<', gallery)
        for image_name in (
            "use-case-monitoring.webp",
            "use-case-sensor-placement.svg",
            "use-case-spatial-view.svg",
            "use-case-climate-analysis.webp",
            "use-case-crop-management.jpg",
            "use-case-data-quality.jpg",
            "use-case-installation-planning.jpg",
        ):
            self.assertIn(image_name, gallery)
        for previous_gallery_image in (
            "greenhouse-hydroponic.jpg",
            "greenhouse-agriculture.jpg",
            "greenhouse-strawberry.jpg",
            "greenhouse-tomatoes.jpg",
            "greenhouse-unsplash-eoj6t-cMtNs.jpg",
        ):
            self.assertNotIn(previous_gallery_image, gallery)
        self.assertIn("센서 데이터 품질 점검", gallery)
        self.assertIn("센서 설치 위치 검토", gallery)
        self.assertLess(
            gallery.index("센서 배치 조합 비교"),
            gallery.index("온실 환경 모니터링"),
        )
        self.assertIn(
            f'<a class="gso-use-case-card" href="{reverse("optimization")}?greenhouse={greenhouse.pk}">',
            gallery[:gallery.index("센서 배치 조합 비교")],
        )
        self.assertIn(
            f'<a class="gso-use-case-card" href="{reverse("analysis")}?greenhouse={greenhouse.pk}">',
            gallery,
        )
        self.assertIn(
            f'<a class="gso-use-case-card" href="{reverse("optimization")}?greenhouse={greenhouse.pk}">',
            gallery,
        )
        self.assertIn(
            f'<a class="gso-use-case-card" href="{reverse("greenhouse-list")}">',
            gallery,
        )
        self.assertIn(
            f'<a class="gso-use-case-card" href="{reverse("simulator")}?greenhouse={greenhouse.pk}">',
            gallery,
        )
        self.assertEqual(gallery.count('class="gso-use-case-image-fallback"'), 7)
        snapshot_start = rendered_dashboard.index('<section class="dashboard-section dashboard-metrics"')
        snapshot_end = rendered_dashboard.index('<!-- ==================================================\n     4. ENVIRONMENT OVERVIEW', snapshot_start)
        snapshot = rendered_dashboard[snapshot_start:snapshot_end]
        self.assertEqual(snapshot.count("data-count-up"), 2)
        self.assertEqual(snapshot.count("data-sparkline="), 2)
        self.assertIn('id="snapshot-temperature-series"', snapshot)
        self.assertIn('id="snapshot-humidity-series"', snapshot)
        self.assertEqual(len(dashboard.context["snapshot_temperature_series"]), 24)
        self.assertEqual(len(dashboard.context["snapshot_humidity_series"]), 24)
        self.assertEqual(
            dashboard.context["sample_temp"],
            round(sum(dashboard.context["snapshot_temperature_series"]) / 24, 1),
        )
        self.assertEqual(
            dashboard.context["sample_humidity"],
            round(sum(dashboard.context["snapshot_humidity_series"]) / 24, 1),
        )
        self.assertIn("SAMPLE DATA", snapshot)
        self.assertIn("실시간 수신 없음", snapshot)
        self.assertContains(dashboard, f'href="{reverse("analysis")}?greenhouse={greenhouse.pk}"')
        self.assertContains(dashboard, f'href="{reverse("optimization")}?greenhouse={greenhouse.pk}"')
        self.assertContains(dashboard, f'href="{reverse("simulator")}?greenhouse={greenhouse.pk}"')
        self.assertContains(dashboard, "data-gallery-next")
        self.assertContains(dashboard, "온실의 지금을 읽다.")
        self.assertContains(dashboard, "온도부터 습도까지, 선택한 온실의 환경 정보를 한눈에 확인해 보세요.")
        self.assertContains(dashboard, "데이터 상태")
        self.assertContains(dashboard, "고정 시드로 생성한 시연용 데이터입니다.")
        self.assertNotContains(dashboard, "선택한 온실 한눈에 보기")
        self.assertEqual(dashboard.content.count(b'class="stat-card"'), 4)
        self.assertContains(dashboard, "primary-navigation")
        self.assertNotContains(dashboard, 'id="sidebar"')
        create_response = self.client.post(reverse("greenhouse-create"), {
            "name": "신규 온실", "shape": "single", "length_m": "12", "width_m": "5",
            "height_m": "3", "ventilation": "측창", "crop": "토마토", "sensor_count": "3",
        })
        self.assertEqual(create_response.status_code, 302)
        self.assertTrue(Greenhouse.objects.filter(name="신규 온실").exists())
        self.assertIsNotNone(greenhouse.pk)
