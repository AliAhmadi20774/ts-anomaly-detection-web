# Scripts

Utility scripts for the time series anomaly detection project.

## generate_version_info.py

Generate `build/windows_version_info.txt` from `src/version.py` before building a Windows EXE. Requires PyInstaller. Run from the project root:

```powershell
.\.venv\Scripts\python.exe scripts/generate_version_info.py
```

See the [EXE build guide](../README_EXE.md) for the build command.

## create_dat_file.py
Create a single .dat file with sample signal data (test1 + test2).

```bash
python create_dat_file.py
```

## create_sample_folder.py
Create a folder with 10 sample .dat files, each containing both test1 and test2.

```bash
python create_sample_folder.py
```

Output: `data/sample_dat_files/`

## create_scenario_dataset.py

Generate independent input folders for every configured device/test, plus a mixed
folder containing all file-based cases. Covers empty/missing/zero signals, length
boundaries, spikes, dropouts, drift, noise, nonfinite values, name filtering and
invalid files. These are synthetic inputs; Normal/Anomaly labels depend on the
model and are not guaranteed.

Run from the project root:

```powershell
.\.venv\Scripts\python.exe scripts/create_scenario_dataset.py --verify
```

Output: `data/scenario_dataset/`. Select a scenario's **input** folder in the GUI
(for example `data/scenario_dataset/device1/03_all_zero/input`). The loader does
not search subfolders. `99_mixed/input` combines all files; individual folders
isolate a single case. The generated README lists every folder.

`manifest.json` records each file's expected loader result and original/padded
length. `verification.json` records checks using the real file loader; it does
not validate model predictions. Empty signals are preserved without zero padding,
excluded from models and displayed as No Data in HTML. No models run when there
are no eligible signals. NaN/Infinity are intentionally included to expose
the current lack of finite-value validation.

The generator uses seed 42 by default and refuses to overwrite an existing
directory. To generate another copy or verify the existing copy:

```powershell
.\.venv\Scripts\python.exe scripts/create_scenario_dataset.py --output data/scenario_dataset_v2 --seed 42 --verify
.\.venv\Scripts\python.exe scripts/create_scenario_dataset.py --verify-only
```
