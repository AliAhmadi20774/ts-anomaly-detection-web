"""Generate several distinct current-format DAT files for preview testing."""

import argparse
import gzip
from pathlib import Path

from .generate_sample_dat import make_payload


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "files" / "batch"
SAMPLE_COUNT = 22528
SCENARIOS = (
    ("01_reference.dat", 1024, 128, 1.0, 1.0),
    ("02_short_delay.dat", 256, 128, 1.0, 1.0),
    ("03_long_delay.dat", 4096, 128, 1.0, 1.0),
    ("04_fast_sine.dat", 1024, 64, 1.0, 1.0),
    ("05_slow_sine.dat", 1024, 256, 1.0, 1.0),
    ("06_high_amplitude.dat", 1024, 128, 2.0, 2.0),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for index, (filename, delay, period, step_level, sine_amplitude) in enumerate(SCENARIOS, 1):
        payload = make_payload(
            "device1", f"SN-BATCH-{index:03d}", ["test1", "test2"],
            "sample-operator", "2026-11-20T10:30:00+03:30",
            SAMPLE_COUNT, delay, period, step_level, sine_amplitude,
        )
        output = args.output_dir / filename
        output.write_bytes(gzip.compress(payload, mtime=0))
        print(f"Created {output.name}: delay={delay}, sine period={period}, step={step_level}, sine amplitude={sine_amplitude}")


if __name__ == "__main__":
    main()
