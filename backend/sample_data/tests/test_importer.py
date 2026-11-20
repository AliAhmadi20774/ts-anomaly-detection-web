import gzip

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APITestCase

from dat_imports.proto import current_pb2
from devices.models import DeviceRun, DeviceType, MeasurementBatch, SignalDefinition, SignalTrace, TestDefinition, TestRun


class DatImportApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = get_user_model().objects.create_superuser(username="import-admin", password="import-test-password")
        device = cls.device = DeviceType.objects.create(name="Motor")
        for name in ("test1", "test2"):
            definition = TestDefinition.objects.create(name=name, device_type=device, sample_rate_hz=1000)
            for signal_name in ("temperature_c", "voltage_v"):
                SignalDefinition.objects.create(name=signal_name, test=definition)

    def setUp(self) -> None:
        self.client.force_authenticate(self.user)
        self.url = reverse("dat-import")

    def post_import(self, data, **kwargs):
        return self.client.post(self.url, {"device_type": str(self.device.pk), **data}, **kwargs)

    def make_upload(self, *, second_date="2026-11-20T10:30:00+03:30", serial="SN-001", extra_serial=None, device_series="Motor"):
        root = current_pb2.Array_ProtoDevice()
        device = root.items.add(deviceSeries=device_series, serialNumber=serial)
        for name, date in (("test1", "2026-11-20T10:30:00+03:30"), ("test2", second_date)):
            test = device.testResult.add(testName=name, operatorName="operator-1", date=date)
            test.signals.add(name="temperature_c").data.extend([20.0, 21.0, 22.0])
            test.signals.add(name="voltage_v").data.extend([11.0, 12.0, 13.0])
            table = test.flatResultDataTable
            table.ColumnNames.extend(["Signal", "RMS"])
            table.ColumnCount = 2
            table.FlattendRows.extend(["temperature_c", "21", "voltage_v", "12"])
        if extra_serial:
            root.items.add(deviceSeries="Unregistered", serialNumber=extra_serial)
        return SimpleUploadedFile("sample.dat", gzip.compress(root.SerializeToString()), content_type="application/octet-stream")

    def test_import_stores_all_samples(self) -> None:
        response = self.post_import({"files": [self.make_upload()]}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["summary"]["test_runs"], 2)
        self.assertEqual(response.data["files"][0]["status"], "imported")
        self.assertEqual(TestRun.objects.count(), 2)
        self.assertEqual(MeasurementBatch.objects.count(), 1)
        self.assertEqual(DeviceRun.objects.count(), 1)
        self.assertEqual(SignalTrace.objects.count(), 4)
        run = TestRun.objects.get(test__name="test1")
        self.assertEqual(run.device_run.test_runs.count(), 2)
        self.assertEqual(run.created_at, run.device_run.batch.created_at)
        self.assertEqual(response.data["batch"]["devices"][0]["serial_number"], "SN-001")
        self.assertEqual(len(response.data["batch"]["devices"][0]["tests"]), 2)
        batch_detail = self.client.get(reverse("measurement-batch-detail", args=[run.device_run.batch_id]))
        self.assertEqual(batch_detail.status_code, 200)
        self.assertEqual(batch_detail.data["devices"][0]["serial_number"], "SN-001")
        self.assertEqual(len(batch_detail.data["devices"][0]["tests"]), 2)
        self.assertEqual(run.source_operator_name, "operator-1")
        self.assertEqual(run.flat_result_data["flattened_rows"], ["temperature_c", "21", "voltage_v", "12"])
        signal = run.signal_traces.get(signal_definition__name="temperature_c")
        self.assertEqual(signal.samples, [20.0, 21.0, 22.0])
        signal_list = self.client.get(reverse("test-run-signals", args=[run.pk]))
        self.assertEqual(signal_list.status_code, 200)
        self.assertEqual(len(signal_list.data), 2)
        detail = self.client.get(reverse("test-run-signal-samples", args=[run.pk, signal.pk]))
        self.assertEqual(detail.data["samples"], signal.samples)

    def test_selected_device_type_is_required_and_mismatched_files_are_rejected(self) -> None:
        missing = self.client.post(self.url, {"files": [self.make_upload()]}, format="multipart")
        self.assertEqual(missing.status_code, 400)
        self.assertIn("device_type", missing.data)
        response = self.post_import({"files": [self.make_upload(device_series="Pump"), self.make_upload()]}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item["status"] for item in response.data["files"]], ["error", "imported"])
        self.assertIn("does not match", response.data["files"][0]["errors"][0])
        self.assertEqual(TestRun.objects.count(), 2)
        self.assertEqual(DeviceRun.objects.count(), 1)
        self.assertEqual(MeasurementBatch.objects.count(), 1)

    def test_same_named_device_type_cannot_import_using_other_definition(self) -> None:
        duplicate = DeviceType.objects.create(name="Motor")
        response = self.client.post(self.url, {"device_type": str(duplicate.pk), "files": [self.make_upload()]}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["files"][0]["status"], "error")
        self.assertIn("registered more than once", response.data["files"][0]["errors"][0])
        self.assertFalse(TestRun.objects.exists())


    def test_same_dat_can_be_imported_in_two_separate_batches(self) -> None:
        first = self.post_import({"files": [self.make_upload()]}, format="multipart")
        second = self.post_import({"files": [self.make_upload()]}, format="multipart")
        self.assertEqual(first.data["files"][0]["status"], "imported")
        self.assertEqual(second.data["files"][0]["status"], "imported")
        self.assertNotEqual(first.data["batch"]["id"], second.data["batch"]["id"])
        self.assertEqual(MeasurementBatch.objects.count(), 2)
        self.assertEqual(DeviceRun.objects.count(), 2)
        self.assertEqual(TestRun.objects.count(), 4)
        self.assertEqual(SignalTrace.objects.count(), 8)
        self.assertEqual(TestRun.objects.order_by().values("source_file_sha256").distinct().count(), 1)

    def test_same_dat_can_appear_twice_in_one_batch(self) -> None:
        response = self.post_import({"files": [self.make_upload(), self.make_upload()]}, format="multipart")
        self.assertEqual([item["status"] for item in response.data["files"]], ["imported", "imported"])
        self.assertEqual(MeasurementBatch.objects.count(), 1)
        self.assertEqual(DeviceRun.objects.count(), 1)
        self.assertEqual(DeviceRun.objects.get().test_runs.count(), 4)

    def test_multiple_files_share_one_batch_timestamp(self) -> None:
        response = self.post_import({"files": [
            self.make_upload(serial="SN-001"), self.make_upload(serial="SN-002"),
        ]}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["summary"]["test_runs"], 4)
        self.assertEqual(MeasurementBatch.objects.count(), 1)
        self.assertEqual(DeviceRun.objects.count(), 2)
        self.assertEqual({run.created_at for run in TestRun.objects.all()}, {MeasurementBatch.objects.get().created_at})
        self.assertEqual({device.test_runs.count() for device in DeviceRun.objects.all()}, {2})

    def test_same_serial_in_multiple_files_stays_under_one_device_run(self) -> None:
        response = self.post_import({"files": [
            self.make_upload(),
            self.make_upload(second_date="2026-11-21T10:30:00+03:30"),
        ]}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["summary"]["test_runs"], 4)
        self.assertEqual(MeasurementBatch.objects.count(), 1)
        self.assertEqual(DeviceRun.objects.count(), 1)
        self.assertEqual(DeviceRun.objects.get().test_runs.count(), 4)

    def test_import_ignores_device_entries_after_index_zero(self) -> None:
        response = self.post_import({"files": [
            self.make_upload(extra_serial="SN-IGNORED"),
        ]}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["summary"]["test_runs"], 2)
        self.assertEqual(list(DeviceRun.objects.values_list("serial_number", flat=True)), ["SN-001"])

    def test_invalid_second_test_rolls_back_whole_file(self) -> None:
        response = self.post_import({"files": [self.make_upload(second_date="bad-date")]}, format="multipart")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["files"][0]["status"], "error")
        self.assertFalse(TestRun.objects.exists())
        self.assertFalse(MeasurementBatch.objects.exists())
        self.assertFalse(SignalTrace.objects.exists())

    def test_missing_definition_is_skipped_and_anonymous_is_forbidden(self) -> None:
        SignalDefinition.objects.filter(test__name="test2", name="voltage_v").delete()
        response = self.post_import({"files": [self.make_upload()]}, format="multipart")
        self.assertEqual(response.data["files"][0]["status"], "skipped")
        self.assertFalse(TestRun.objects.exists())
        self.client.force_authenticate(None)
        self.assertEqual(self.post_import({"files": [self.make_upload()]}, format="multipart").status_code, 403)
