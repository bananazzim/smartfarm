from django.test import TestCase
from django.urls import reverse

from greenhouses.models import Greenhouse
from notifications.models import AlertEvent, AlertSetting


class NotificationWorkflowTests(TestCase):
    def setUp(self):
        self.greenhouse = Greenhouse.objects.create(name="알림 테스트", length_m=12, width_m=5, height_m=3)

    def test_mock_event_saves_settings_and_history_without_external_delivery(self):
        response = self.client.post(reverse("notifications"), {
            "greenhouse": self.greenhouse.pk,
            "phone": "010-1234-5678",
            "temperature_min": "10",
            "temperature_max": "30",
            "humidity_min": "40",
            "humidity_max": "85",
            "simulate": "1",
        })
        self.assertRedirects(response, reverse("notifications"))
        setting = AlertSetting.objects.get(greenhouse=self.greenhouse)
        event = AlertEvent.objects.get(greenhouse=self.greenhouse)
        self.assertEqual(setting.phone, "010-1234-5678")
        self.assertEqual(event.status, "mock_sent")
        self.assertIn("[DEMO 알림]", event.message)

    def test_invalid_thresholds_are_not_saved(self):
        response = self.client.post(reverse("notifications"), {
            "greenhouse": self.greenhouse.pk,
            "phone": "",
            "temperature_min": "35",
            "temperature_max": "30",
            "humidity_min": "40",
            "humidity_max": "85",
            "simulate": "1",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(AlertSetting.objects.exists())
        self.assertFalse(AlertEvent.objects.exists())
