from devices.models import DeviceType, TestDefinition
from dat_imports.reader import DatReadError, DatReader


class DatPreviewService:
    def __init__(self) -> None:
        self.reader = DatReader()
        self.definitions = {}
        for definition in TestDefinition.objects.select_related("device_type").prefetch_related("signals"):
            key = (definition.device_type.name, definition.name)
            self.definitions.setdefault(key, []).append(definition)

    @staticmethod
    def device_type_error(data: dict, selected_device_type) -> str | None:
        series = data["devices"][0]["device_series"]
        if series != selected_device_type.name:
            return f"DAT device type '{series}' does not match selected device type '{selected_device_type.name}'."
        if DeviceType.objects.filter(name=series).exclude(pk=selected_device_type.pk).exists():
            return f"Device type name '{series}' is registered more than once; the DAT cannot identify which one it belongs to."
        return None

    def preview(self, files: list, file_format: str, selected_device_type) -> dict:
        results = []
        for index, uploaded_file in enumerate(files):
            result = {"index": index, "name": uploaded_file.name, "size": uploaded_file.size}
            try:
                _, data = self.reader.read(uploaded_file, file_format)
                mismatch = self.device_type_error(data, selected_device_type)
                if mismatch:
                    results.append({**result, **data, "status": "error", "error": mismatch})
                else:
                    warnings = self.check_definitions(data, selected_device_type)
                    results.append({**result, **data, "status": "warning" if warnings else "ready", "warnings": warnings})
            except DatReadError as error:
                results.append({**result, "status": "error", "error": str(error)})

        valid = [result for result in results if result["status"] in ("ready", "warning")]
        devices = [device for result in valid for device in result["devices"]]
        tests = [test for device in devices for test in device["tests"]]
        signals = [signal for test in tests for signal in test["signals"]]
        summary = {
            "files": len(results), "readable": len(valid),
            "errors": sum(result["status"] == "error" for result in results),
            "devices": len({(device["device_series"], device["serial_number"]) for device in devices}),
            "tests": len(tests), "signals": len(signals),
        }
        return {"summary": summary, "files": results}

    def check_definitions(self, data: dict, selected_device_type) -> list[str]:
        warnings = []
        for device in data["devices"]:
            if not device["tests"]:
                warnings.append(f"{device['serial_number']}: no tests are present.")
            for test in device["tests"]:
                label = f"{device['serial_number']} / {test['name']}"
                definitions = [definition for definition in self.definitions.get((device["device_series"], test["name"]), [])
                               if definition.device_type_id == selected_device_type.pk]
                definition = definitions[0] if len(definitions) == 1 else None
                test["test_definition_id"] = str(definition.pk) if definition else None
                test["sample_rate_hz"] = definition.sample_rate_hz if definition else None

                if not definition:
                    warnings.append(f"{label}: no unique matching test definition; sample rate is unavailable.")
                else:
                    defined_names = [signal.name for signal in definition.signals.all()]
                    for signal in test["signals"]:
                        if defined_names.count(signal["name"]) != 1:
                            warnings.append(f"{label}: signal '{signal['name']}' has no unique matching definition.")

                if not test["operator_name"]:
                    warnings.append(f"{label}: operator name is not present in the file.")
                if not test["date_raw"]:
                    warnings.append(f"{label}: execution date is not present in the file.")
                if not test["signals"]:
                    warnings.append(f"{label}: no signals are present.")
                for signal in test["signals"]:
                    if not signal["sample_count"]:
                        warnings.append(f"{label} / {signal['name']}: the signal has no samples.")
                    if signal["non_finite_count"]:
                        warnings.append(f"{label} / {signal['name']}: the signal contains NaN or infinite values.")
                if test["flat_result_table"] and not test["flat_result_table"]["valid_shape"]:
                    warnings.append(f"{label}: the flat results table has inconsistent rows or columns.")
        return warnings
