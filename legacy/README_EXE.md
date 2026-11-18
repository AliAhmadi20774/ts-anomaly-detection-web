# Build a Windows EXE

Requires **64-bit Windows and Python 3.13**. Keep the configured models in `checkpoints/`. Close the application before rebuilding.

## Copy and Build

Open PowerShell in the project folder containing `main.py`, then copy and run this entire block. It installs dependencies, reads the version automatically, and builds the EXE without a console window:

```powershell
if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed" }
}
.\.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }

.\.venv\Scripts\python.exe scripts/generate_version_info.py
if ($LASTEXITCODE -ne 0) { throw "Version metadata generation failed" }

.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onedir --windowed --name TSAnomalyDetector --version-file "build/windows_version_info.txt" --add-data "checkpoints:checkpoints" --collect-data plotly main.py
if ($LASTEXITCODE -ne 0) { throw "EXE build failed" }
```

The result is `dist/TSAnomalyDetector/TSAnomalyDetector.exe`. A new build replaces the previous output. Internet access is needed to install dependencies that are not already available.

## Version Example

The version comes from `src/version.py`; no version needs to be typed into the commands. For example, with `__version__ = "0.1.0"`:

| Location | Version |
| --- | --- |
| Application window title | `v0.1.0` |
| EXE Properties > Details > File version | `0.1.0.0` |
| EXE Properties > Details > Product version | `0.1.0` |

For a new release, change only `src/version.py` and rerun the build block above. The fourth Windows component stays `0` automatically.

## Run and Share

Copy and run from the project folder:

```powershell
Push-Location .\dist\TSAnomalyDetector
try {
    .\TSAnomalyDetector.exe
} finally {
    Pop-Location
}
```

Check the window title, EXE version details, and analysis with sample `.dat` files. Reports are saved under `outputs/` in the working directory; with the command above, this is `dist/TSAnomalyDetector/outputs`.

Share the **entire `dist/TSAnomalyDetector` folder** as a ZIP. The EXE alone is insufficient. Python is not required on the destination computer; test the bundle there before distributing it. This is a portable app, not an installer.

If startup fails, rebuild with `--console` instead of `--windowed` to see errors. If a model is missing, check `dist/TSAnomalyDetector/_internal/checkpoints/`.

[PyInstaller documentation](https://pyinstaller.org/en/stable/usage.html) | [Windows version resources](https://pyinstaller.org/en/stable/usage.html#capturing-windows-version-data)
