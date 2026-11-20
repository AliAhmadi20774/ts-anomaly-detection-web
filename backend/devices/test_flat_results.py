from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from devices.models import DeviceType, TestDefinition, TestRun


class FlatResultStorageTests(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = get_user_model().objects.create_superuser(username="table-admin", password="table-test-password")
        cls.device = DeviceType.objects.create(name="Motor")
        cls.definition = TestDefinition.objects.create(name="Vibration", device_type=cls.device, sample_rate_hz=1000)

    def setUp(self) -> None:
        self.client.force_authenticate(self.user)
        self.url = reverse("test-run-list")
        self.payload = {"test": str(self.definition.pk), "device_serial_number": "SN-TABLE", "executed_at": "2026-11-19T08:30:00Z"}
        self.table = {"columns": ["Name", "Value"], "column_count": 2, "flattened_rows": ["RMS", "001.20", "Peak", "", "Label", "نتیجه"]}

    def create_run(self, table) -> TestRun:
        response = self.client.post(self.url, {**self.payload, "flat_result_data": table}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return TestRun.objects.get(pk=response.data["id"])

    def test_strings_are_preserved_and_metadata_edits_do_not_replace_the_table(self) -> None:
        run = self.create_run(self.table)
        detail = reverse("test-run-detail", args=[run.pk])
        self.assertEqual(self.client.patch(detail, {"executed_at": "2026-11-20T08:30:00Z"}, format="json").status_code, 200)
        run.refresh_from_db()
        self.assertEqual(run.flat_result_data, self.table)
        self.assertNotIn("flat_result_data", self.client.get(self.url).data["results"][0])

    def test_missing_null_and_empty_tables_are_supported(self) -> None:
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(TestRun.objects.get(pk=response.data["id"]).flat_result_data)
        self.assertIsNone(self.create_run(None).flat_result_data)

        empty = {"columns": [], "column_count": 0, "flattened_rows": []}
        run = self.create_run(empty)
        self.assertEqual(run.flat_result_data, empty)
        detail = reverse("test-run-detail", args=[run.pk])
        self.assertEqual(self.client.patch(detail, {"flat_result_data": None}, format="json").status_code, 200)
        run.refresh_from_db()
        self.assertIsNone(run.flat_result_data)

    def test_invalid_table_shapes_and_non_string_cells_are_rejected(self) -> None:
        for invalid in (
            [], {}, "not-a-table",
            {**self.table, "column_count": -1},
            {**self.table, "column_count": True},
            {**self.table, "column_count": 3},
            {**self.table, "flattened_rows": ["partial row"]},
            {**self.table, "flattened_rows": ["RMS", 1.2]},
            {**self.table, "columns": ["Name", None]},
        ):
            with self.subTest(table=invalid):
                response = self.client.post(self.url, {**self.payload, "flat_result_data": invalid}, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn("flat_result_data", response.data)
        self.assertFalse(TestRun.objects.exists())

    def test_table_updates_require_the_change_permission(self) -> None:
        run = self.create_run(self.table)
        user = get_user_model().objects.create_user(username="table-reader")
        self.client.force_authenticate(user)
        response = self.client.patch(reverse("test-run-detail", args=[run.pk]), {"flat_result_data": None}, format="json")
        self.assertEqual(response.status_code, 403)
        run.refresh_from_db()
        self.assertEqual(run.flat_result_data, self.table)
