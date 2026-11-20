# Current-format DAT samples

`multi_signal_current.dat` is a synthetic, gzip-compressed Protocol Buffers file for the web DAT preview. It contains one `device1` device (`SN-MULTI-001`) with `test1` and `test2`. Each test has four sensor signals of 22,528 aligned samples:

| Test | Signal | Unit | Synthetic value | Shape |
| --- | --- | --- | --- | --- |
| `test1` | `temperature_c` | °C | 20 + 5 × step | Step |
| `test1` | `voltage_v` | V | 12 + sine | Sine |
| `test1` | `pressure_kpa` | kPa | 100 + 3 × delayed sine | Delayed sine |
| `test1` | `current_a` | A | 2 × delayed step | Delayed step |
| `test2` | `humidity_pct` | % | 40 + 20 × step | Step |
| `test2` | `vibration_mm_s` | mm/s | 1.5 × sine | Sine |
| `test2` | `flow_l_min` | L/min | 10 + 2 × delayed sine | Delayed sine |
| `test2` | `speed_rpm` | rpm | 1,500 × delayed step | Delayed step |

The step starts at sample 5,632, the sine period is 128 samples, and the delay is 1,024 samples in the reference file. The delayed waveform component has a zero prefix; any sensor baseline remains present. Names encode the measured quantity and unit because the current DAT format has no separate sensor or unit field. These sensor assignments are illustrative, not real hardware metadata. Each test also has an operator, a date, and a valid flat result table with RMS and absolute peak per signal. The waveforms are examples, not labeled anomaly ground truth.

The `batch/` directory contains six additional, distinct files. Every file has one device, `test1` and `test2`, and the same eight sensor names by test, so one set of definitions can match the whole batch. Each file uses a different serial number.

| File | Delay (samples) | Sine period (samples) | Step level | Sine amplitude |
| --- | ---: | ---: | ---: | ---: |
| `01_reference.dat` | 1,024 | 128 | 1 | 1 |
| `02_short_delay.dat` | 256 | 128 | 1 | 1 |
| `03_long_delay.dat` | 4,096 | 128 | 1 | 1 |
| `04_fast_sine.dat` | 1,024 | 64 | 1 | 1 |
| `05_slow_sine.dat` | 1,024 | 256 | 1 | 1 |
| `06_high_amplitude.dat` | 1,024 | 128 | 2 | 2 |

The DAT file has this structure:

- Root: repeated devices (`items`).
- Device: `deviceSeries`, `serialNumber`, repeated `testResult`. The project reads only the first root `items[0]` device entry from each DAT file.
- Test: `testName`, `operatorName`, `date`, repeated `signals`, `flatResultDataTable`.
- Signal: `name`, repeated numeric `data` samples.
- Flat result table: `ColumnNames`, `FlattendRows`, `ColumnCount`. These samples use the columns `Signal`, `RMS`, and `PeakAbs`, with one row per signal.

Sample rate is not stored in the DAT schema. The preview obtains it from a matching test definition in the database. Delays in this dataset are measured in samples, not seconds.

To regenerate the files after installing `backend/requirements.txt`, run from the `backend` directory:

```powershell
python -m sample_data.generate_sample_dat
python -m sample_data.generate_sample_batch
```

Use `--help` on the single-file generator to set the output path, device, serial number, one or two test names, sample count, delay, sine period, step level, and sine amplitude. The batch generator accepts `--output-dir`. In the web DAT page, select **Detect format** or **Current format**, preview the files, then import the ready current-format files. To avoid definition warnings, register the `device1` device type, `test1` and `test2` test definitions, and the four sensor names listed above under each respective test first.

Import requires a timezone-aware ISO 8601 date in each test. One import request creates one measurement batch. Each serial number in that batch has its own device run containing test runs, and each test run has four stored signal traces. The batch receipt timestamp is shared by all its tests. The source file name and operator are retained. The same DAT can be imported again in a new batch. Legacy DAT files remain preview-only because they do not contain the execution metadata needed for import.
