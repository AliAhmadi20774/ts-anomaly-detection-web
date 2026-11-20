"""Import validated current-format DAT measurements into test runs."""

from hashlib import sha256

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from dat_imports.preview import DatPreviewService
from dat_imports.reader import DatReadError
from devices.models import DeviceRun, MeasurementBatch, SignalTrace, TestRun


class DatImportService:
    def __init__(self) -> None:
        self.preview_service = DatPreviewService()

    def import_files(self, files: list, user, selected_device_type) -> dict:
        results = []
        batch = None
        for uploaded_file in files:
            result = {"name": uploaded_file.name}
            try:
                payload, data = self.preview_service.reader.read(
                    uploaded_file, "current", include_full_table=True, include_samples=True,
                )
                mismatch = self.preview_service.device_type_error(data, selected_device_type)
                if mismatch:
                    raise ValueError(mismatch)
                digest = sha256(payload).hexdigest()
                warnings = self.preview_service.check_definitions(data, selected_device_type)
                if warnings:
                    result.update(status="skipped", test_runs=0, errors=warnings)
                else:
                    batch, run_ids = self._save_file(data, digest, uploaded_file.name, user, batch, selected_device_type)
                    result.update(status="imported", test_runs=len(run_ids), run_ids=run_ids)
            except (DatReadError, ValueError) as error:
                result.update(status="error", test_runs=0, errors=[str(error)])
            results.append(result)

        batch_data = None
        if batch is not None:
            batch_data = {
                "id": str(batch.pk),
                "created_at": batch.created_at.isoformat(),
                "devices": [
                    {
                        "id": str(device.pk),
                        "device_type": device.device_type.name,
                        "serial_number": device.serial_number,
                        "tests": [
                            {"id": str(run.pk), "name": run.test.name, "executed_at": run.executed_at.isoformat()}
                            for run in device.test_runs.all()
                        ],
                    }
                    for device in batch.devices.select_related("device_type").prefetch_related("test_runs__test")
                ],
            }
        return {
            "batch": batch_data,
            "summary": {
                "files": len(results),
                "imported": sum(item["status"] == "imported" for item in results),
                "skipped": sum(item["status"] == "skipped" for item in results),
                "errors": sum(item["status"] == "error" for item in results),
                "test_runs": sum(item["test_runs"] for item in results),
            },
            "files": results,
        }

    @transaction.atomic
    def _save_file(self, data: dict, digest: str, file_name: str, user, batch: MeasurementBatch | None, selected_device_type) -> tuple[MeasurementBatch, list[str]]:
        prepared = []
        for device_index, device in enumerate(data["devices"]):
            for test_index, test in enumerate(device["tests"]):
                definitions = self.preview_service.definitions[(device["device_series"], test["name"])]
                definition = next(item for item in definitions if item.device_type_id == selected_device_type.pk)
                signal_definitions = {signal.name: signal for signal in definition.signals.all()}
                signal_names = [signal["name"] for signal in test["signals"]]
                if len(signal_names) != len(set(signal_names)):
                    raise ValueError(f"{device['serial_number']} / {test['name']}: duplicate signal names.")
                executed_at = parse_datetime(test["date_raw"] or "")
                if executed_at is None or not timezone.is_aware(executed_at):
                    raise ValueError(f"{device['serial_number']} / {test['name']}: use an ISO 8601 date with timezone.")
                if len(test["operator_name"] or "") > 255:
                    raise ValueError(f"{device['serial_number']} / {test['name']}: operator name is too long.")
                prepared.append((device_index, test_index, device, test, definition, signal_definitions, executed_at))

        if batch is None:
            batch = MeasurementBatch.objects.create(recorded_by=user)

        run_ids = []
        devices = {}
        for device_index, test_index, device, test, definition, signal_definitions, executed_at in prepared:
            device_key = (definition.device_type_id, device["serial_number"])
            if device_key not in devices:
                devices[device_key], _ = DeviceRun.objects.get_or_create(
                    batch=batch,
                    device_type_id=definition.device_type_id,
                    serial_number=device["serial_number"],
                )
            run = TestRun.objects.create(
                test=definition,
                device_run=devices[device_key],
                executed_at=executed_at,
                recorded_by=user,
                flat_result_data=test.get("flat_result_data"),
                source_file_name=file_name[:255],
                source_file_sha256=digest,
                source_device_index=device_index,
                source_test_index=test_index,
                source_operator_name=test["operator_name"] or "",
            )
            SignalTrace.objects.bulk_create([
                SignalTrace(
                    test_run=run,
                    signal_definition=signal_definitions[signal["name"]],
                    samples=signal["samples"],
                )
                for signal in test["signals"]
            ])
            run_ids.append(str(run.pk))
        return batch, run_ids
