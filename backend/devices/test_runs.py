from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db.models.deletion import ProtectedError
from django.urls import reverse
from rest_framework.test import APITestCase

from devices.models import DeviceType, TestDefinition, TestRun


class TestRunApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = get_user_model().objects.create_superuser(username="run-admin", password="test-run-password")
        cls.reader = get_user_model().objects.create_user(username="run-reader")
        cls.reader.user_permissions.add(Permission.objects.get(codename="view_testrun"))
        cls.device = DeviceType.objects.create(name="Motor")
        cls.definition = TestDefinition.objects.create(name="Vibration", device_type=cls.device, sample_rate_hz=1000)

    def setUp(self) -> None:
        self.client.force_authenticate(self.user)
        self.url = reverse("test-run-list")
        self.data = {
            "test": str(self.definition.pk),
            "device_serial_number": "SN-001",
            "executed_at": "2026-11-19T08:30:00Z",
            "notes": "Baseline measurement",
        }

    def create_run(self) -> TestRun:
        response = self.client.post(self.url, self.data, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return TestRun.objects.get(pk=response.data["id"])

    def test_server_assigns_recorder_and_sampling_snapshot(self) -> None:
        self.data.update({"recorded_by": self.reader.pk, "sample_rate_hz": 12, "device_type": str(uuid4())})

        run = self.create_run()

        self.assertEqual(run.recorded_by, self.user)
        self.assertEqual(run.device_type, self.device)
        self.assertEqual(run.sample_rate_hz, 1000)
        self.assertEqual(run.notes, "Baseline measurement")

    def test_snapshot_survives_changes_to_test_definition(self) -> None:
        run = self.create_run()
        other_device = DeviceType.objects.create(name="Pump")

        self.definition.device_type = other_device
        self.definition.sample_rate_hz = 500
        self.definition.save()

        run.refresh_from_db()
        self.assertEqual(run.sample_rate_hz, 1000)
        self.assertEqual(run.device_type, self.device)

        run.notes = "Updated note"
        run.save()
        run.refresh_from_db()

        self.assertEqual(run.sample_rate_hz, 1000)

    def test_serial_date_and_parent_are_validated(self) -> None:
        for invalid in (
            {"device_serial_number": "  "},
            {"device_serial_number": "x" * 129},
            {"test": str(self.device.pk)},
            {"executed_at": "not-a-date"},
        ):
            with self.subTest(invalid=invalid):
                response = self.client.post(self.url, {**self.data, **invalid}, format="json")
                self.assertEqual(response.status_code, 400)

        self.assertFalse(TestRun.objects.exists())

    def test_edit_keeps_test_and_server_metadata_unchanged(self) -> None:
        run = self.create_run()
        detail = reverse("test-run-detail", args=[run.pk])

        response = self.client.patch(
            detail,
            {
                "notes": "Corrected",
                "device_serial_number": "SN-002",
                "recorded_by": self.reader.pk,
                "sample_rate_hz": 10,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        run.refresh_from_db()
        self.assertEqual(run.notes, "Corrected")
        self.assertEqual(run.device_serial_number, "SN-002")
        self.assertEqual(run.sample_rate_hz, 1000)
        self.assertEqual(run.recorded_by, self.user)

        other_test = TestDefinition.objects.create(name="Other test", device_type=self.device, sample_rate_hz=500)
        response = self.client.patch(detail, {"test": str(other_test.pk)}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_runs_can_repeat_and_be_filtered_and_searched(self) -> None:
        first = self.create_run()
        self.create_run()

        response = self.client.get(
            self.url,
            {
                "test": str(self.definition.pk),
                "device_type": str(self.device.pk),
                "search": "SN-001",
                "page_size": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["recorded_by_code"], "run-admin")
        self.assertEqual(self.client.get(self.url, {"search": "missing"}).data["count"], 0)
        self.assertEqual(self.client.delete(reverse("test-run-detail", args=[first.pk])).status_code, 204)

    def test_run_protects_referenced_test_device_and_recorder(self) -> None:
        self.create_run()
        response = self.client.delete(reverse("test-definition-detail", args=[self.definition.pk]))
        self.assertEqual(response.status_code, 409)

        for obj in (self.device, self.user):
            with self.subTest(model=type(obj).__name__):
                with self.assertRaises(ProtectedError):
                    obj.delete()

    def test_read_permission_does_not_grant_write_access(self) -> None:
        self.client.force_authenticate(self.reader)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.post(self.url, self.data, format="json").status_code, 403)

        self.reader.user_permissions.clear()
        self.client.force_authenticate(get_user_model().objects.get(pk=self.reader.pk))
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_anonymous_requests_are_rejected(self) -> None:
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 403)
