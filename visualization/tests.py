from django.test import TestCase
from django.urls import reverse

from greenhouses.models import Greenhouse


class SimulatorSelectionTests(TestCase):
    def setUp(self):
        self.first_greenhouse = Greenhouse.objects.create(
            name="첫 번째 온실",
            length_m=20,
            width_m=6,
            height_m=3,
        )
        self.selected_greenhouse = Greenhouse.objects.create(
            name="선택 온실",
            length_m=24,
            width_m=7,
            height_m=3.5,
        )

    def test_simulator_uses_selected_greenhouse(self):
        response = self.client.get(
            reverse("simulator"),
            {"greenhouse": self.selected_greenhouse.pk},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["greenhouse"], self.selected_greenhouse)
        self.assertContains(response, "선택 온실")

    def test_simulator_rejects_invalid_greenhouse_instead_of_showing_another(self):
        for greenhouse_id in ("invalid", "999"):
            with self.subTest(greenhouse_id=greenhouse_id):
                response = self.client.get(
                    reverse("simulator"),
                    {"greenhouse": greenhouse_id},
                )

                self.assertEqual(response.status_code, 404)

    def test_demo_is_explicit_and_does_not_generate_recommendation_coordinates(self):
        response = self.client.get(reverse("simulator"), {"mode": "demo"})
        self.assertTrue(response.context['is_demo'])
        self.assertContains(response,'id="gso-fps"')
        self.assertTrue(all(s['positionType']=='measured' for s in response.context['simulator_data']['sensors']))

    def test_root_and_real_routes_render_real_empty_state_without_demo_fallback(self):
        for params in ({}, {"mode": "real", "greenhouse": self.first_greenhouse.pk}):
            response = self.client.get(reverse("simulator"), params)
            self.assertEqual(response.status_code,200)
            self.assertFalse(response.context['is_demo'])
            self.assertEqual(response.context['simulator_data']['sensors'],[])
            self.assertEqual(response.context['simulator_data']['records'],[])
