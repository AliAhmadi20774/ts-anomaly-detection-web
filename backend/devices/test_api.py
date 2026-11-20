from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from devices.models import DeviceType, SignalDefinition, TestDefinition


class DefinitionApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.administrator = get_user_model().objects.create_superuser(
            username="1", password="test-api-password"
        )
        cls.regular_user = get_user_model().objects.create_user(
            username="002", password="test-api-password"
        )
        cls.device = DeviceType.objects.create(name="device1")
        cls.other_device = DeviceType.objects.create(name="device2")
        cls.test = TestDefinition.objects.create(
            name="test1", device_type=cls.device, sample_rate_hz=1000
        )
        cls.other_test = TestDefinition.objects.create(
            name="test1", device_type=cls.other_device, sample_rate_hz=500
        )
        cls.signal = SignalDefinition.objects.create(name="signal1", test=cls.test)
        cls.other_signal = SignalDefinition.objects.create(
            name="signal1", test=cls.other_test
        )

    def setUp(self) -> None:
        self.client.force_authenticate(self.administrator)

    def test_anonymous_access_is_rejected(self) -> None:
        self.client.force_authenticate(user=None)
        for name in ("device-type-list", "test-definition-list", "signal-definition-list"):
            with self.subTest(route=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_admin_can_create_read_update_and_delete_a_hierarchy(self) -> None:
        supplied_id = str(uuid4())
        response = self.client.post(reverse("device-type-list"), {
            "name": " device3 ", "id": supplied_id,
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "device3")
        device_id = response.data["id"]
        self.assertNotEqual(device_id, supplied_id)

        response = self.client.post(reverse("test-definition-list"), {
            "name": "test2", "device_type": device_id, "sample_rate_hz": 1000,
        }, format="json")
        self.assertEqual(response.status_code, 201)
        test_id = response.data["id"]

        response = self.client.post(reverse("signal-definition-list"), {
            "name": "signal2", "test": test_id,
        }, format="json")
        self.assertEqual(response.status_code, 201)
        signal_id = response.data["id"]

        signal_url = reverse("signal-definition-detail", args=[signal_id])
        self.assertEqual(self.client.get(signal_url).json()["test"], test_id)
        response = self.client.put(signal_url, {
            "name": "renamed", "test": test_id,
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "renamed")

        test_url = reverse("test-definition-detail", args=[test_id])
        response = self.client.patch(test_url, {"sample_rate_hz": 12.5}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["sample_rate_hz"], 12.5)

        self.assertEqual(self.client.delete(signal_url).status_code, 204)
        self.assertEqual(self.client.delete(test_url).status_code, 204)
        self.assertEqual(
            self.client.delete(reverse("device-type-detail", args=[device_id])).status_code,
            204,
        )

    def test_invalid_parents_return_field_errors(self) -> None:
        cases = [
            ("test-definition-list", {
                "name": "test", "device_type": str(self.test.id), "sample_rate_hz": 1000,
            }, "device_type"),
            ("test-definition-list", {
                "name": "test", "device_type": str(uuid4()), "sample_rate_hz": 1000,
            }, "device_type"),
            ("signal-definition-list", {
                "name": "signal", "test": str(self.device.id),
            }, "test"),
            ("signal-definition-list", {
                "name": "signal", "test": "invalid",
            }, "test"),
        ]
        for route, payload, field in cases:
            with self.subTest(route=route, payload=payload):
                response = self.client.post(reverse(route), payload, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)

    def test_invalid_sample_rates_return_field_errors(self) -> None:
        url = reverse("test-definition-detail", args=[self.test.id])
        for rate in (0, -1, None, "NaN", "Infinity", "-Infinity"):
            with self.subTest(rate=rate):
                response = self.client.patch(url, {"sample_rate_hz": rate}, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn("sample_rate_hz", response.data)
        self.test.refresh_from_db()
        self.assertEqual(self.test.sample_rate_hz, 1000)

    def test_duplicate_definition_names_are_rejected_with_validation_errors(self) -> None:
        second_test = TestDefinition.objects.create(
            name="test2", device_type=self.device, sample_rate_hz=1000
        )
        second_signal = SignalDefinition.objects.create(name="signal2", test=second_test)
        cases = [
            ("test-definition-list", {"name": "test1", "device_type": str(self.device.id), "sample_rate_hz": 500}),
            ("signal-definition-list", {"name": "signal1", "test": str(self.test.id)}),
        ]
        for route, payload in cases:
            with self.subTest(route=route):
                response = self.client.post(reverse(route), payload, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn("non_field_errors", response.data)

        response = self.client.patch(
            reverse("test-definition-detail", args=[second_test.id]),
            {"name": "test1"}, format="json",
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.patch(
            reverse("signal-definition-detail", args=[second_signal.id]),
            {"name": "signal1", "test": str(self.test.id)}, format="json",
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.post(reverse("signal-definition-list"), {
            "name": "signal1", "test": str(second_test.id),
        }, format="json")
        self.assertEqual(response.status_code, 201)

    def test_blank_names_and_missing_fields_are_rejected(self) -> None:
        cases = [
            ("device-type-list", {"name": " "}),
            ("test-definition-list", {
                "name": " ", "device_type": str(self.device.id), "sample_rate_hz": 1000,
            }),
            ("signal-definition-list", {"name": " ", "test": str(self.test.id)}),
            ("test-definition-list", {"name": "missing parents and sample rate"}),
            ("signal-definition-list", {"name": "missing parent"}),
        ]
        for route, payload in cases:
            with self.subTest(route=route):
                response = self.client.post(reverse(route), payload, format="json")
                self.assertEqual(response.status_code, 400)

    def test_parent_filters_search_and_invalid_filter(self) -> None:
        response = self.client.get(reverse("test-definition-list"), {
            "device_type": str(self.device.id),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in response.data["results"]], [str(self.test.id)]
        )
        response = self.client.get(reverse("signal-definition-list"), {
            "test": str(self.other_test.id),
        })
        self.assertEqual(
            [item["id"] for item in response.data["results"]], [str(self.other_signal.id)]
        )
        response = self.client.get(reverse("device-type-list"), {"search": "device2"})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.other_device.id))
        self.assertEqual(
            self.client.get(reverse("test-definition-list"), {
                "device_type": "invalid",
            }).status_code, 400,
        )

    def test_protected_delete_returns_conflict(self) -> None:
        for route, identifier in (
            ("device-type-detail", self.device.id),
            ("test-definition-detail", self.test.id),
        ):
            with self.subTest(route=route):
                response = self.client.delete(reverse(route, args=[identifier]))
                self.assertEqual(response.status_code, 409)
        self.assertTrue(SignalDefinition.objects.filter(pk=self.signal.pk).exists())

    def test_reads_and_writes_require_separate_model_permissions(self) -> None:
        url = reverse("device-type-list")
        self.client.force_authenticate(self.regular_user)
        self.assertEqual(self.client.get(url).status_code, 403)

        view_permission = Permission.objects.get(
            content_type__app_label="devices", codename="view_devicetype"
        )
        self.regular_user.user_permissions.add(view_permission)
        user = get_user_model().objects.get(pk=self.regular_user.pk)
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(
            self.client.post(url, {"name": "forbidden"}, format="json").status_code, 403,
        )

        add_permission = Permission.objects.get(
            content_type__app_label="devices", codename="add_devicetype"
        )
        user.user_permissions.add(add_permission)
        self.client.force_authenticate(get_user_model().objects.get(pk=user.pk))
        self.assertEqual(
            self.client.post(url, {"name": "allowed"}, format="json").status_code, 201,
        )
        detail_url = reverse("device-type-detail", args=[self.device.id])
        self.assertEqual(
            self.client.patch(detail_url, {"name": "forbidden"}, format="json").status_code,
            403,
        )
        self.assertEqual(self.client.delete(detail_url).status_code, 403)

    def test_list_is_paginated_and_page_size_is_bounded(self) -> None:
        DeviceType.objects.bulk_create(
            [DeviceType(name=f"device-{index:03}") for index in range(105)]
        )
        response = self.client.get(reverse("device-type-list"))
        self.assertEqual(response.data["count"], 107)
        self.assertEqual(len(response.data["results"]), 50)
        self.assertIsNotNone(response.data["next"])
        response = self.client.get(reverse("device-type-list"), {"page_size": 1000})
        self.assertEqual(len(response.data["results"]), 100)

    def test_unknown_identifier_returns_not_found(self) -> None:
        for identifier in (str(uuid4()), "invalid"):
            with self.subTest(identifier=identifier):
                response = self.client.get(
                    reverse("device-type-detail", args=[identifier])
                )
                self.assertEqual(response.status_code, 404)

    def test_session_authentication_requires_csrf_for_writes(self) -> None:
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.administrator)
        url = reverse("device-type-list")
        response = client.post(url, {"name": "without-token"}, format="json")
        self.assertEqual(response.status_code, 403)

        client.get(reverse("admin:index"))
        token = client.cookies["csrftoken"].value
        response = client.post(
            url, {"name": "with-token"}, format="json", HTTP_X_CSRFTOKEN=token
        )
        self.assertEqual(response.status_code, 201)
