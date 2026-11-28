from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from rest_framework.test import APITestCase

from devices.models import DeviceRun, DeviceType, MeasurementBatch


class MeasurementBatchFilterTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="batch-reader")
        cls.user.user_permissions.add(Permission.objects.get(codename="view_measurementbatch"))
        cls.motor = DeviceType.objects.create(name="Motor")
        cls.sensor = DeviceType.objects.create(name="Sensor")
        cls.unused = DeviceType.objects.create(name="Unused")
        cls.motor_batches = []
        for index, device_type in enumerate([cls.motor, cls.sensor, cls.motor, cls.sensor]):
            batch = MeasurementBatch.objects.create(recorded_by=cls.user)
            for serial in [f"SN-{index}-001", f"SN-{index}-002"]:
                DeviceRun.objects.create(batch=batch, device_type=device_type, serial_number=serial)
            if device_type == cls.motor:
                cls.motor_batches.append(str(batch.pk))

    def setUp(self):
        self.client.force_authenticate(self.user)
        self.url = reverse("measurement-batch-list")

    def test_filter_is_distinct_and_applied_before_pagination(self):
        response = self.client.get(self.url, {"device_type": self.motor.pk, "page_size": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        first = response.data["results"][0]
        self.assertEqual(len(first["devices"]), 2)
        self.assertTrue(all(device["device_type"] == self.motor.pk for device in first["devices"]))
        second_page = self.client.get(self.url, {"device_type": self.motor.pk, "page_size": 1, "page": 2})
        self.assertEqual(second_page.status_code, 200)
        self.assertCountEqual([first["id"], second_page.data["results"][0]["id"]], self.motor_batches)

    def test_clear_filter_and_device_without_batches(self):
        self.assertEqual(self.client.get(self.url).data["count"], 4)
        self.assertEqual(self.client.get(self.url, {"device_type": ""}).data["count"], 4)
        response = self.client.get(self.url, {"device_type": self.unused.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_serial_search_matches_batches_and_combines_with_device_filter(self):
        response = self.client.get(self.url, {"search": "sn-2"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"][0]["devices"]), 2)
        response = self.client.get(self.url, {"search": "SN-2", "device_type": self.sensor.pk})
        self.assertEqual(response.data["count"], 0)
        response = self.client.get(self.url, {"search": "SN-2", "device_type": self.motor.pk})
        self.assertEqual(response.data["count"], 1)
        response = self.client.get(self.url, {"search": "SN-", "page_size": 1})
        self.assertEqual(response.data["count"], 4)
        self.assertEqual(len(response.data["results"]), 1)

    def test_invalid_or_unknown_device_is_a_field_error(self):
        for identifier in ["not-a-uuid", str(uuid4())]:
            with self.subTest(identifier=identifier):
                response = self.client.get(self.url, {"device_type": identifier})
                self.assertEqual(response.status_code, 400)
                self.assertIn("device_type", response.data)

    def test_filter_does_not_bypass_batch_permission(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.url, {"device_type": self.motor.pk}).status_code, 403)
        self.user.user_permissions.clear()
        self.client.force_authenticate(get_user_model().objects.get(pk=self.user.pk))
        self.assertEqual(self.client.get(self.url, {"device_type": self.motor.pk}).status_code, 403)
