import gzip
import math
import zlib

from google.protobuf.message import DecodeError

from dat_imports.proto import current_pb2, legacy_pb2


class DatReadError(ValueError):
    pass


class DatReader:
    max_file_bytes = 32 * 1024 * 1024
    max_decoded_bytes = 64 * 1024 * 1024
    schemas = {"current": current_pb2.Array_ProtoDevice, "legacy": legacy_pb2.Array_ProtoDevice}

    def read(self, uploaded_file, file_format: str = "auto", *, include_full_table: bool = False, include_samples: bool = False) -> tuple[bytes, dict]:
        if not uploaded_file.name.lower().endswith(".dat"):
            raise DatReadError("Select a .dat file.")
        if uploaded_file.size > self.max_file_bytes:
            raise DatReadError("The file exceeds the 32 MiB upload limit.")

        try:
            with gzip.GzipFile(fileobj=uploaded_file) as compressed:
                payload = compressed.read(self.max_decoded_bytes + 1)
        except (OSError, EOFError, zlib.error) as error:
            raise DatReadError("The file is not a valid gzip-compressed DAT file.") from error

        if len(payload) > self.max_decoded_bytes:
            raise DatReadError("The decoded file exceeds the 64 MiB limit.")
        if not payload:
            raise DatReadError("The file contains no data.")

        if file_format != "auto":
            return payload, self.parse(payload, file_format, include_full_table=include_full_table, include_samples=include_samples)

        candidates = []
        for version in self.schemas:
            try:
                candidates.append(self.parse(payload, version, include_full_table=include_full_table, include_samples=include_samples))
            except DatReadError:
                continue

        if len(candidates) == 1:
            return payload, candidates[0]
        if len(candidates) > 1:
            raise DatReadError("The format is ambiguous. Select Current or Legacy explicitly.")
        raise DatReadError("The file does not match either supported DAT format.")

    def parse(self, payload: bytes, version: str, *, include_full_table: bool = False, include_samples: bool = False) -> dict:
        root = self.schemas[version]()
        try:
            root.ParseFromString(payload)
        except DecodeError as error:
            raise DatReadError("The file does not match the selected DAT format.") from error

        if not root.items:
            raise DatReadError("The file contains no devices.")

        devices = []
        has_test_content = False
        # This project uses only the first device entry from each DAT file.
        for device in root.items[:1]:
            series = self.read_name(device.deviceSeries, "Device series")
            serial = self.read_name(device.serialNumber, "Device serial number")
            tests = []
            for test in device.testResult:
                name = self.read_name(test.testName, "Test name")
                operator = self.read_name(test.operatorName, "Operator name", required=False) if version == "current" else None
                date = self.read_name(test.date, "Test date", required=False) if version == "current" else None
                table = self.preview_table(test.flatResultDataTable) if version == "current" and test.HasField("flatResultDataTable") else None
                signals = [self.preview_signal(signal, include_samples=include_samples) for signal in test.signals]
                has_test_content = has_test_content or bool(signals or operator or date or table)
                tests.append({"name": name, "operator_name": operator, "date_raw": date, "signals": signals, "flat_result_table": table})
                if include_full_table:
                    tests[-1]["flat_result_data"] = self.read_table(test.flatResultDataTable) if table is not None else None
            devices.append({"device_series": series, "serial_number": serial, "tests": tests})

        if not has_test_content:
            raise DatReadError("The file contains no signals or test metadata for the selected format.")
        return {"format": version, "devices": devices}

    def read_name(self, value: str, label: str, required: bool = True) -> str | None:
        if not value.strip():
            if required:
                raise DatReadError(f"{label} is missing.")
            return None
        if any(ord(character) < 32 for character in value):
            raise DatReadError(f"{label} contains invalid control characters.")
        return value

    def preview_signal(self, signal, *, include_samples: bool = False) -> dict:
        name = self.read_name(signal.name, "Signal name")
        invalid_count = sum(not math.isfinite(value) for value in signal.data)
        sample = [value if math.isfinite(value) else None for value in signal.data[:5]]
        result = {"name": name, "sample_count": len(signal.data), "non_finite_count": invalid_count, "sample": sample}
        if include_samples:
            result["samples"] = list(signal.data)
        return result

    def preview_table(self, table) -> dict:
        columns = list(table.ColumnNames)
        width = table.ColumnCount
        cell_count = len(table.FlattendRows)
        valid_shape = width >= 0 and ((width == 0 and not columns and not cell_count) or (width > 0 and len(columns) == width and cell_count % width == 0))
        rows = [list(table.FlattendRows[start:start + width]) for start in range(0, min(cell_count, width * 5), width)] if width > 0 else []
        return {"columns": columns, "column_count": width, "row_count": cell_count // width if width > 0 else 0, "sample_rows": rows, "valid_shape": valid_shape}

    def read_table(self, table) -> dict:
        return {"columns": list(table.ColumnNames), "column_count": table.ColumnCount, "flattened_rows": list(table.FlattendRows)}
