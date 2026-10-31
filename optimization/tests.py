from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from greenhouses.models import Greenhouse
from .engine import evaluate_combinations


class OptimizationEngineTests(SimpleTestCase):
    def test_combinations_use_time_ordered_holdout_and_return_three_sensors(self):
        result = evaluate_combinations(sensor_count=3)
        self.assertEqual(result["combination_count"], 20)
        self.assertEqual(len(result["recommended"]["sensors"]), 3)
        self.assertLess(result["train_end"], result["validation_start"])
        self.assertGreaterEqual(result["recommended"]["test"]["temperature"]["mae"], 0)


class OptimizationPagesTests(TestCase):
    def test_key_pages_render_with_demo_notice(self):
        Greenhouse.objects.create(name="페이지 테스트 온실", length_m=12, width_m=5, height_m=3)
        for name, expected in (
            ("optimization", "샘플 데이터 분석 결과"),
            ("simulator", "3D 시뮬레이터"),
            ("report", "검증 예정"),
            ("notifications", "MOCK ONLY"),
        ):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, expected)

    def test_optimization_uses_selected_greenhouse(self):
        selected_greenhouse = Greenhouse.objects.create(
            name="선택한 최적화 온실",
            length_m=24,
            width_m=7,
            height_m=3.5,
        )

        response = self.client.get(
            reverse("optimization"),
            {"greenhouse": selected_greenhouse.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["greenhouse"], selected_greenhouse)
        self.assertContains(response, "선택한 최적화 온실")
