"""Generate reproducible GUI-ready .dat scenarios for every configured test.

Run from any directory with the project's Python environment. Each scenario's
input folder is independent because the application does not scan recursively.
"""

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from proto.generated.schema_pb2 import Array_ProtoDevice
from src.config.global_config import CONFIG


SIGNAL_CASES = {
    "baseline": "Small finite noise around zero; synthetic reference, not a guaranteed Normal.",
    "sine": "Sine wave with small noise, at the expected length.",
    "all_zero": "Every sample is exactly zero, at the expected length.",
    "empty_signal": "signal1 exists but its data array is empty; retained for No Data reporting and never evaluated by a model.",
    "single_sample": "One nonzero sample; remaining samples are padded with zeros.",
    "short_signal": "Half the expected length; loader pads the missing tail with zeros.",
    "one_sample_short": "Expected length minus one, to exercise the length boundary.",
    "one_sample_long": "Expected length plus one; loader keeps the extra sample.",
    "long_signal": "Expected length plus 1000; loader does not truncate it.",
    "short_all_zero": "Half-length all-zero signal; both zero data and length mismatch.",
    "constant_nonzero": "Constant positive signal without variation.",
    "constant_negative": "Constant negative signal without variation.",
    "near_zero": "Tiny nonzero values; distinguishes near-zero from exactly all-zero.",
    "single_spike": "One large spike in the middle of the signal.",
    "negative_spike": "One large negative spike in the middle of the signal.",
    "spike_each_section": "A large spike at the midpoint of every configured section.",
    "zero_section": "A complete configured section is zero inside a nonzero signal.",
    "zero_tail": "Final quarter is zero while the stored length remains correct.",
    "step_change": "A sudden level shift halfway through the signal.",
    "drift": "Gradually increasing offset across the whole signal.",
    "high_noise": "Large-amplitude random noise.",
    "nan_value": "One NaN sample; current loader accepts it without finite-value validation.",
    "positive_infinity": "One positive infinity; current loader accepts it.",
    "negative_infinity": "One negative infinity; current loader accepts it.",
}
STRUCTURE_CASES = {
    "missing_tests": "Device exists but testResult is empty; loader skips the file.",
    "unknown_test": "Only an unconfigured test exists; loader skips the file.",
    "missing_signals": "Configured tests exist but have no signals; loader skips the file.",
    "wrong_signal_name": "Only signal2 exists; loader skips the file.",
    "uppercase_signal": "Signal1 spelling is accepted by the current loader.",
    "wrong_device": "Device series does not match the selected device; loader skips it.",
    "empty_root": "Valid compressed protobuf with no device items; loader skips it.",
    "invalid_gzip": "File is not gzip; loader logs a decoding error and skips it.",
    "invalid_protobuf": "Gzip is valid but its contents are invalid protobuf; loader logs an error and skips it.",
    "zero_byte_file": "File has zero bytes; loader skips it.",
    "ignored_extension": "Valid gzip/protobuf stored as .dat.gz; directory loader ignores it.",
    "empty_folder": "No .dat files exist; no models run and the dashboard has no serial rows.",
}
ACCEPTED_STRUCTURE_CASES = {"uppercase_signal"}


def signal_values(case, expected_length, sections, rng):
    length = {
        "empty_signal": 0,
        "single_sample": 1,
        "short_signal": expected_length // 2,
        "short_all_zero": expected_length // 2,
        "one_sample_short": expected_length - 1,
        "one_sample_long": expected_length + 1,
        "long_signal": expected_length + 1000,
    }.get(case, expected_length)
    if case in {"all_zero", "short_all_zero"}:
        return [0.0] * length
    if case in {"constant_nonzero", "constant_negative", "near_zero"}:
        value = {"constant_nonzero": 2.0, "constant_negative": -2.0, "near_zero": 1e-10}[case]
        return [value] * length
    if case == "high_noise":
        return [rng.gauss(0, 5) for _ in range(length)]
    values = [rng.uniform(-0.0001, 0.0001) for _ in range(length)]
    if case in {"sine", "zero_section", "zero_tail"}:
        values = [math.sin(2 * math.pi * i / 100) + value for i, value in enumerate(values)]
    if case == "single_sample":
        values = [1.0]
    if case in {"single_spike", "negative_spike", "nan_value", "positive_infinity", "negative_infinity"}:
        values[length // 2] = {
            "single_spike": 20.0, "negative_spike": -20.0,
            "nan_value": float("nan"), "positive_infinity": float("inf"),
            "negative_infinity": -float("inf"),
        }[case]
    if case == "spike_each_section":
        for section in sections.values():
            position = (section["start"] + min(section["end"], length)) // 2
            if 0 <= position < length:
                values[position] = 20.0
    if case == "zero_section":
        section_name = next(iter(sections))
        section = sections[section_name]
        for i in range(section["start"], min(section["end"], length)):
            values[i] = 0.0
    if case == "zero_tail":
        values[3 * length // 4:] = [0.0] * (length - 3 * length // 4)
    if case == "step_change":
        values = [value + (3.0 if i >= length // 2 else 0) for i, value in enumerate(values)]
    if case == "drift":
        values = [value + 4.0 * i / max(1, length - 1) for i, value in enumerate(values)]
    return values


def create_file(path, device, tests, case, serial, seed):
    root = Array_ProtoDevice()
    metadata = {}
    rng = random.Random(seed)
    if case != "empty_root":
        item = root.items.add()
        item.deviceSeries = "UNCONFIGURED_DEVICE" if case == "wrong_device" else device
        item.serialNumber = serial
        for test_name, cfg in tests.items():
            if case == "missing_tests" or case == f"missing_{test_name}":
                metadata[test_name] = {"accepted": False}
                continue
            test = item.testResult.add()
            test.testName = "UNCONFIGURED_TEST" if case == "unknown_test" else test_name
            if case != "missing_signals":
                signal = test.signals.add()
                signal.name = {"wrong_signal_name": "signal2", "uppercase_signal": "Signal1"}.get(case, "signal1")
                values = signal_values(case, cfg["expected_len"], cfg["sections"], rng)
                signal.data.extend(values)
            accepted = case in SIGNAL_CASES or case in ACCEPTED_STRUCTURE_CASES or case.startswith("missing_") and case not in STRUCTURE_CASES
            entry = {"accepted": accepted}
            if accepted:
                actual_length = len(signal.data)
                entry.update({
                    "signal_length": actual_length,
                    "expected_length": cfg["expected_len"],
                    "loaded_length": max(actual_length, cfg["expected_len"]) if actual_length else 0,
                    "length_matches_expected": actual_length == cfg["expected_len"],
                    "all_zero_after_loading": all(value == 0 for value in signal.data),
                    "nonfinite_count": sum(not math.isfinite(value) for value in signal.data),
                })
            metadata[test_name] = entry
    if case in {"empty_root", "invalid_gzip", "invalid_protobuf", "zero_byte_file", "ignored_extension"}:
        metadata = {test: {"accepted": False} for test in tests}
    if case == "invalid_gzip":
        payload = b"Deliberately invalid gzip scenario\n"
    elif case == "zero_byte_file":
        payload = b""
    else:
        raw = b"\xff" if case == "invalid_protobuf" else root.SerializeToString()
        payload = gzip.compress(raw, mtime=0)
    path.write_bytes(payload)
    return {"path": path.name, "serial_number": serial, "sha256": hashlib.sha256(payload).hexdigest(), "tests": metadata}


def verify_dataset(output):
    """Verify each file using the real loader, without running model inference."""
    from src.data.loader import process_file_threaded

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    checks = 0
    logged_errors = []
    for scenario in manifest["scenarios"]:
        input_dir = output / scenario["input_folder"]
        assert input_dir.is_dir(), input_dir
        for file in scenario["files"]:
            path = input_dir / file["path"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == file["sha256"], path
            for test, expected in file["tests"].items():
                if path.suffix.lower() != ".dat":
                    assert not expected["accepted"]
                    checks += 1
                    continue
                result = process_file_threaded(str(path), [test], [scenario["device"]], logged_errors.append)
                assert (result is not None) == expected["accepted"], (path, test, expected)
                if result is not None:
                    assert result["serial_number"] == file["serial_number"]
                    for field in ("signal_length", "expected_length", "length_matches_expected"):
                        assert result[field] == expected[field], (path, test, field)
                    values = result["signal_list"]
                    assert len(values) == expected["loaded_length"], (path, test)
                    assert all(value == 0 for value in values) == expected["all_zero_after_loading"], (path, test)
                    assert sum(not math.isfinite(value) for value in values) == expected["nonfinite_count"], (path, test)
                checks += 1
    result = {"status": "passed", "file_test_checks": checks, "expected_decode_errors": len(logged_errors), "model_inference_run": False}
    (output / "verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def generate_dataset(output, seed=42):
    # Refuse to reuse a directory, so earlier data is never overwritten or mixed.
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"seed": seed, "source": "synthetic", "model_labels_guaranteed": False, "scenarios": []}
    for device, tests in CONFIG.items():
        cases = {**SIGNAL_CASES, **STRUCTURE_CASES}
        for test in tests:
            cases[f"missing_{test}"] = f"Only {test} is absent; other configured tests remain available."
        mixed_sources = []
        for index, (case, description) in enumerate(cases.items(), start=1):
            folder = output / device / f"{index:02d}_{case}" / "input"
            folder.mkdir(parents=True)
            files = []
            if case == "empty_folder":
                # Keep this input folder available after cloning the repository.
                (folder / ".gitkeep").touch()
            else:
                suffix = ".dat.gz" if case == "ignored_extension" else ".dat"
                path = folder / (case + suffix)
                entry = create_file(path, device, tests, case, f"SC_{index:02d}_{case}", seed + index)
                files.append(entry)
                mixed_sources.append((path, entry))
            manifest["scenarios"].append({"device": device, "scenario": case, "description": description,
                "input_folder": folder.relative_to(output).as_posix(), "files": files})
        folder = output / device / "99_mixed" / "input"
        folder.mkdir(parents=True)
        files = []
        for source, entry in mixed_sources:
            (folder / source.name).write_bytes(source.read_bytes())
            files.append(entry)
        manifest["scenarios"].append({"device": device, "scenario": "mixed", "description": "All file-based cases together, including valid, missing, nonfinite and corrupt data.",
            "input_folder": folder.relative_to(output).as_posix(), "files": files})
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    lines = [
        "# Scenario Dataset", "",
        "These inputs are synthetic. Scenario names do not guarantee Normal or Anomaly model results.", "",
        "Select the matching device and a scenario's `input` folder in the application, then run a single test or batch.",
        "The loader does not search subfolders. Do not select the root dataset folder as input.", "",
        "The `99_mixed/input` folder combines all files. Files contain all configured tests except cases that deliberately omit a test or signal.", "",
        "Empty signals never enter a model and appear as No Data in HTML reports. No models run when no eligible samples exist. NaN and Infinity are currently accepted by the loader and may invalidate model results.", "",
        "`manifest.json` records original and loaded lengths, expected loader acceptance and scenario descriptions.",
        "`verification.json` records checks with the real loader. It does not verify model inference or predicted labels.", "",
        "| Device | Scenario | Input folder | Description |", "|---|---|---|---|",
    ]
    for scenario in manifest["scenarios"]:
        lines.append(f"| {scenario['device']} | {scenario['scenario']} | `{scenario['input_folder']}` | {scenario['description']} |")
    (output / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data" / "scenario_dataset")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--verify", action="store_true", help="Check generated files with the real loader.")
    parser.add_argument("--verify-only", action="store_true", help="Verify an existing dataset without writing input files.")
    args = parser.parse_args()
    output = args.output.resolve()
    if not args.verify_only:
        manifest = generate_dataset(output, args.seed)
        print(f"Created {len(manifest['scenarios'])} scenario folders at {output}")
    if args.verify or args.verify_only:
        print(json.dumps(verify_dataset(output), indent=2))


if __name__ == "__main__":
    main()
