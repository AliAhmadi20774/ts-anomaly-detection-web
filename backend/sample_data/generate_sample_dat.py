"""Generate a current-format DAT file with several aligned signals per test.

Run from the backend directory with ``python -m sample_data.generate_sample_dat``.
Install ``backend/requirements.txt`` first.
"""

import argparse
import gzip
import math
from pathlib import Path

from dat_imports.proto import current_pb2


DEFAULT_OUTPUT = Path(__file__).resolve().parent / "files" / "multi_signal_current.dat"
RESULT_COLUMNS = (
    "Signal", "Window", "Start sample", "End sample", "Samples", "Mean",
    "RMS", "Min", "Max", "PeakAbs", "StdDev", "PeakToPeak",
)
SENSOR_PROFILES = (
    (
        ("temperature_c", "step", 20.0, 5.0),
        ("voltage_v", "sine", 12.0, 1.0),
        ("pressure_kpa", "sine_delayed", 100.0, 3.0),
        ("current_a", "step_delayed", 0.0, 2.0),
    ),
    (
        ("humidity_pct", "step", 40.0, 20.0),
        ("vibration_mm_s", "sine", 0.0, 1.5),
        ("flow_l_min", "sine_delayed", 10.0, 2.0),
        ("speed_rpm", "step_delayed", 0.0, 1500.0),
    ),
)


def make_signals(
    sample_count: int,
    delay_samples: int,
    sine_period: int,
    step_level: float = 1.0,
    sine_amplitude: float = 1.0,
) -> dict[str, list[float]]:
    if sample_count < 4:
        raise ValueError("Sample count must be at least 4.")
    if not 0 < delay_samples < sample_count - sample_count // 4:
        raise ValueError("Delay must be positive and leave room for the delayed step.")
    if sine_period < 2:
        raise ValueError("Sine period must be at least 2 samples.")
    if not all(math.isfinite(value) and value > 0 for value in (step_level, sine_amplitude)):
        raise ValueError("Step level and sine amplitude must be finite positive numbers.")

    step_at = sample_count // 4
    step = [0.0 if index < step_at else step_level for index in range(sample_count)]
    sine = [sine_amplitude * math.sin(2 * math.pi * index / sine_period) for index in range(sample_count)]

    def delayed(values: list[float]) -> list[float]:
        return [0.0] * delay_samples + values[: sample_count - delay_samples]

    return {
        "step": step,
        "sine": sine,
        "sine_delayed": delayed(sine),
        "step_delayed": delayed(step),
    }


def make_sensor_signals(test_index: int, waveforms: dict[str, list[float]]) -> dict[str, list[float]]:
    """Give each synthetic sensor a measurement, unit, and waveform."""
    profile = SENSOR_PROFILES[test_index]
    return {
        name: [baseline + scale * value for value in waveforms[shape]]
        for name, shape, baseline, scale in profile
    }


def make_result_rows(signals: dict[str, list[float]]) -> list[list[str]]:
    """Summarize each complete signal and four consecutive sample windows."""
    rows = []
    for name, values in signals.items():
        count = len(values)
        window_count = min(4, count)
        windows = [("All samples", 0, count)] + [
            (f"Window {index + 1:02d}", index * count // window_count, (index + 1) * count // window_count)
            for index in range(window_count)
        ]
        for label, start, stop in windows:
            samples = values[start:stop]
            mean = math.fsum(samples) / len(samples)
            rms = math.sqrt(math.fsum(value * value for value in samples) / len(samples))
            deviation = math.sqrt(math.fsum((value - mean) ** 2 for value in samples) / len(samples))
            low, high = min(samples), max(samples)
            rows.append([
                name, label, str(start), str(stop - 1), str(len(samples)),
                f"{mean:.6f}", f"{rms:.6f}", f"{low:.6f}", f"{high:.6f}",
                f"{max(abs(low), abs(high)):.6f}", f"{deviation:.6f}", f"{high - low:.6f}",
            ])
    return rows


def make_payload(
    device_series: str,
    serial_number: str,
    test_names: list[str],
    operator_name: str,
    date: str,
    sample_count: int,
    delay_samples: int,
    sine_period: int,
    step_level: float = 1.0,
    sine_amplitude: float = 1.0,
) -> bytes:
    if not all((device_series.strip(), serial_number.strip(), operator_name.strip(), date.strip())):
        raise ValueError("Device, serial number, operator, and date must be nonempty.")
    if (not test_names or len(test_names) > len(SENSOR_PROFILES)
            or any(not name.strip() for name in test_names) or len(set(test_names)) != len(test_names)):
        raise ValueError("Provide one or two unique, nonempty test names.")

    waveforms = make_signals(sample_count, delay_samples, sine_period, step_level, sine_amplitude)
    root = current_pb2.Array_ProtoDevice()
    device = root.items.add(deviceSeries=device_series, serialNumber=serial_number)
    for index, name in enumerate(test_names):
        signals = make_sensor_signals(index, waveforms)
        test = device.testResult.add(testName=name, operatorName=operator_name, date=date)
        table = test.flatResultDataTable
        table.ColumnNames.extend(RESULT_COLUMNS)
        table.ColumnCount = len(RESULT_COLUMNS)
        for signal_name, values in signals.items():
            test.signals.add(name=signal_name).data.extend(values)
        for row in make_result_rows(signals):
            table.FlattendRows.extend(row)
    return root.SerializeToString()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--device-series", default="device1")
    parser.add_argument("--serial-number", default="SN-MULTI-001")
    parser.add_argument("--tests", nargs="+", default=["test1", "test2"])
    parser.add_argument("--operator", default="sample-operator")
    parser.add_argument("--date", default="2026-11-20T10:30:00+03:30")
    parser.add_argument("--samples", type=int, default=22528)
    parser.add_argument("--delay-samples", type=int, default=1024)
    parser.add_argument("--sine-period", type=int, default=128)
    parser.add_argument("--step-level", type=float, default=1.0)
    parser.add_argument("--sine-amplitude", type=float, default=1.0)
    args = parser.parse_args()

    try:
        payload = make_payload(
            args.device_series, args.serial_number, args.tests, args.operator,
            args.date, args.samples, args.delay_samples, args.sine_period,
            args.step_level, args.sine_amplitude,
        )
    except ValueError as error:
        parser.error(str(error))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(gzip.compress(payload, mtime=0))
    print(f"Created {args.output} ({len(args.tests)} tests, 4 signals per test, {args.samples} samples per signal).")


if __name__ == "__main__":
    main()
