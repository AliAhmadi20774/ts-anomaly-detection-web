import gzip

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APITestCase

from dat_imports.proto import current_pb2
from dat_imports.reader import DatReader
from devices.models import DeviceType, TestDefinition, TestRun


class DatTableStorageTests(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = get_user_model().objects.create_superuser(username="dat-table-admin", password="table-test-password")
        cls.device = DeviceType.objects.create(name="Motor")
        cls.definition = TestDefinition.objects.create(name="Vibration", device_type=cls.device, sample_rate_hz=1000)

    def test_full_dat_table_is_stored_beyond_the_five_preview_rows(self) -> None:
        self.client.force_authenticate(self.user)
        root = current_pb2.Array_ProtoDevice()
        device = root.items.add(deviceSeries="Motor", serialNumber="SN-TABLE")
        test = device.testResult.add(testName="Vibration")
        test.signals.add(name="signal1").data.append(1.0)
        test.flatResultDataTable.ColumnNames.extend(["Name", "Value"])
        test.flatResultDataTable.ColumnCount = 2
        cells = [cell for row in range(20) for cell in (f"Row {row}", f"00{row}.20")]
        test.flatResultDataTable.FlattendRows.extend(cells)

        upload = SimpleUploadedFile("table.dat", gzip.compress(root.SerializeToString()))
        _, data = DatReader().read(upload, include_full_table=True)
        parsed_test = data["devices"][0]["tests"][0]
        self.assertEqual(len(parsed_test["flat_result_table"]["sample_rows"]), 5)

        payload = {
            "test": str(self.definition.pk), "device_serial_number": "SN-TABLE",
            "executed_at": "2026-11-19T08:30:00Z", "flat_result_data": parsed_test["flat_result_data"],
        }
        response = self.client.post(reverse("test-run-list"), payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        run = TestRun.objects.get(pk=response.data["id"])
        self.assertEqual(run.flat_result_data["flattened_rows"], cells)
        self.assertEqual(len(run.flat_result_data["flattened_rows"]), 40)
        self.assertEqual(self.client.get(reverse("test-run-detail", args=[run.pk])).data["flat_result_data"], run.flat_result_data)
