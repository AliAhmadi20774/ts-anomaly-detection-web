import gzip

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from dat_imports.proto import current_pb2, legacy_pb2
from dat_imports.reader import DatReadError, DatReader
from devices.models import DeviceType, SignalDefinition, TestDefinition, TestRun


def make_payload(version="current", metadata=True, serial="SN-001") -> bytes:
    schema = current_pb2 if version == "current" else legacy_pb2
    root = schema.Array_ProtoDevice()
    device = root.items.add(deviceSeries="Motor", serialNumber=serial)
    test = device.testResult.add(testName="Vibration")
    if version == "current" and metadata:
        test.operatorName = "Operator 007"
        test.date = "1405/08/28 10:30"
        table = test.flatResultDataTable
        table.ColumnNames.extend(["Name", "Value"])
        table.FlattendRows.extend(["RMS", "1.2", "Peak", "3.4"])
        table.ColumnCount = 2
    test.signals.add(name="signal1").data.extend([1.0, 2.0, 3.0])
    test.signals.add(name="temperature").data.extend([20.0, 21.0])
    return root.SerializeToString()


def make_upload(payload=None, name="sample.dat") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, gzip.compress(payload if payload is not None else make_payload()), content_type="application/octet-stream")


class DatReaderTests(SimpleTestCase):
    def setUp(self) -> None:
        self.reader = DatReader()

    def test_current_format_reads_metadata_and_flat_table(self) -> None:
        _, data = self.reader.read(make_upload())
        self.assertEqual(data["format"], "current")
        test = data["devices"][0]["tests"][0]
        self.assertEqual(test["operator_name"], "Operator 007")
        self.assertEqual(test["date_raw"], "1405/08/28 10:30")
        self.assertEqual([signal["name"] for signal in test["signals"]], ["signal1", "temperature"])
        self.assertEqual(test["flat_result_table"]["sample_rows"], [["RMS", "1.2"], ["Peak", "3.4"]])
        self.assertTrue(test["flat_result_table"]["valid_shape"])

    def test_legacy_signals_are_not_misread_as_operator_names(self) -> None:
        _, data = self.reader.read(make_upload(make_payload("legacy")))
        self.assertEqual(data["format"], "legacy")
        test = data["devices"][0]["tests"][0]
        self.assertIsNone(test["operator_name"])
        self.assertIsNone(test["date_raw"])
        self.assertIsNone(test["flat_result_table"])
        self.assertEqual(len(test["signals"]), 2)

    def test_current_format_can_omit_new_metadata(self) -> None:
        _, data = self.reader.read(make_upload(make_payload(metadata=False)))
        self.assertEqual(data["format"], "current")
        self.assertIsNone(data["devices"][0]["tests"][0]["operator_name"])

    def test_only_first_device_and_all_its_tests_are_read(self) -> None:
        root = current_pb2.Array_ProtoDevice.FromString(make_payload())
        root.items[0].testResult.add(testName="Second test").signals.add(name="pressure").data.append(5)
        root.items.add(deviceSeries="Pump", serialNumber="SN-002").testResult.add(testName="Temperature").signals.add(name="temperature").data.append(22)
        _, data = self.reader.read(make_upload(root.SerializeToString()))
        self.assertEqual(len(data["devices"]), 1)
        self.assertEqual(data["devices"][0]["serial_number"], "SN-001")
        self.assertEqual(len(data["devices"][0]["tests"]), 2)

    def test_invalid_numeric_values_are_reported_and_json_safe(self) -> None:
        root = current_pb2.Array_ProtoDevice.FromString(make_payload())
        root.items[0].testResult[0].signals[0].data.extend([float("nan"), float("inf")])
        _, data = self.reader.read(make_upload(root.SerializeToString()))
        signal = data["devices"][0]["tests"][0]["signals"][0]
        self.assertEqual(signal["non_finite_count"], 2)
        self.assertEqual(signal["sample"], [1, 2, 3, None, None])

    def test_wrong_format_corrupt_files_and_missing_names_are_rejected(self) -> None:
        for upload, file_format in (
            (make_upload(make_payload("legacy")), "current"),
            (SimpleUploadedFile("bad.dat", b"not-gzip"), "auto"),
            (make_upload(b"\xff\xff"), "auto"),
            (make_upload(b""), "auto"),
            (make_upload(name="bad.txt"), "auto"),
        ):
            with self.subTest(name=upload.name, file_format=file_format):
                with self.assertRaises(DatReadError):
                    self.reader.read(upload, file_format)
        root = current_pb2.Array_ProtoDevice.FromString(make_payload())
        root.items[0].serialNumber = ""
        with self.assertRaises(DatReadError):
            self.reader.read(make_upload(root.SerializeToString()))

    def test_compressed_and_decoded_size_limits_are_enforced(self) -> None:
        self.reader.max_file_bytes = 1
        with self.assertRaisesMessage(DatReadError, "upload limit"):
            self.reader.read(make_upload())
        self.reader.max_file_bytes = 1024 * 1024
        self.reader.max_decoded_bytes = 10
        with self.assertRaisesMessage(DatReadError, "decoded file exceeds"):
            self.reader.read(make_upload())


class DatPreviewApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = get_user_model().objects.create_superuser(username="preview-user", password="preview-test-password")
        cls.reader = get_user_model().objects.create_user(username="preview-reader")
        cls.device = DeviceType.objects.create(name="Motor")
        cls.definition = TestDefinition.objects.create(name="Vibration", device_type=cls.device, sample_rate_hz=1000)
        SignalDefinition.objects.create(name="signal1", test=cls.definition)
        SignalDefinition.objects.create(name="temperature", test=cls.definition)

    def setUp(self) -> None:
        self.client.force_authenticate(self.user)
        self.url = reverse("dat-preview")

    def post_preview(self, data, **kwargs):
        return self.client.post(self.url, {"device_type": str(self.device.pk), **data}, **kwargs)

    def test_batch_reports_each_file_and_does_not_create_records(self) -> None:
        response = self.post_preview({"files": [make_upload(), make_upload(make_payload("legacy"), "old.dat"), SimpleUploadedFile("bad.dat", b"bad")]}, format="multipart")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"], {"files": 3, "readable": 2, "errors": 1, "devices": 1, "tests": 2, "signals": 4})
        self.assertEqual([item["status"] for item in response.data["files"]], ["ready", "warning", "error"])
        self.assertEqual(response.data["previewed_by_code"], "preview-user")
        self.assertEqual(response.data["files"][0]["devices"][0]["tests"][0]["sample_rate_hz"], 1000)
        self.assertEqual(TestRun.objects.count(), 0)
        self.assertEqual(DeviceType.objects.count(), 1)

    def test_identical_payloads_are_both_previewed(self) -> None:
        payload = make_payload()
        files = [make_upload(payload, "first.dat"), SimpleUploadedFile("second.dat", gzip.compress(payload, mtime=123))]
        response = self.post_preview({"files": files}, format="multipart")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["readable"], 2)
        self.assertEqual([item["status"] for item in response.data["files"]], ["ready", "ready"])
        self.assertEqual(response.data["files"][0]["devices"], response.data["files"][1]["devices"])

    def test_selected_device_type_is_required_and_mismatch_is_error(self) -> None:
        missing = self.client.post(self.url, {"files": [make_upload()]}, format="multipart")
        self.assertEqual(missing.status_code, 400)
        self.assertIn("device_type", missing.data)
        root = current_pb2.Array_ProtoDevice.FromString(make_payload())
        root.items[0].deviceSeries = "Pump"
        response = self.post_preview({"files": [make_upload(root.SerializeToString())]}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["files"][0]["status"], "error")
        self.assertIn("does not match", response.data["files"][0]["error"])
        self.assertEqual(response.data["summary"]["readable"], 0)

    def test_unknown_definitions_and_malformed_table_are_visible(self) -> None:
        root = current_pb2.Array_ProtoDevice.FromString(make_payload())
        test = root.items[0].testResult[0]
        test.testName = "Unconfigured"
        test.flatResultDataTable.ColumnCount = 3
        response = self.post_preview({"files": [make_upload(root.SerializeToString())]}, format="multipart")
        self.assertEqual(response.status_code, 200)
        result = response.data["files"][0]
        self.assertEqual(result["status"], "warning")
        self.assertIsNone(result["devices"][0]["tests"][0]["sample_rate_hz"])
        self.assertTrue(any("inconsistent" in warning for warning in result["warnings"]))

    def test_empty_files_are_reported_individually(self) -> None:
        response = self.post_preview({"files": [SimpleUploadedFile("empty.dat", b""), make_upload()]}, format="multipart")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["files"][0]["status"], "error")
        self.assertEqual(response.data["summary"]["readable"], 1)

    def test_anonymous_and_insufficiently_authorized_requests_are_rejected(self) -> None:
        self.client.force_authenticate(None)
        self.assertEqual(self.post_preview({"files": [make_upload()]}, format="multipart").status_code, 403)
        self.client.force_authenticate(self.reader)
        self.assertEqual(self.post_preview({"files": [make_upload()]}, format="multipart").status_code, 403)
        permissions = Permission.objects.filter(codename__in=["add_testrun", "view_devicetype", "view_testdefinition", "view_signaldefinition"])
        self.reader.user_permissions.add(*permissions)
        self.client.force_authenticate(get_user_model().objects.get(pk=self.reader.pk))
        self.assertEqual(self.post_preview({"files": [make_upload()]}, format="multipart").status_code, 200)

    def test_missing_files_and_invalid_format_are_rejected(self) -> None:
        self.assertEqual(self.post_preview({}, format="multipart").status_code, 400)
        self.assertEqual(self.post_preview({"files": [make_upload()], "file_format": "unknown"}, format="multipart").status_code, 400)
