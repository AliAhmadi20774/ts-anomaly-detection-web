"""Generate PyInstaller's Windows version resource from the application version."""

from pathlib import Path
import re
import runpy

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    version = runpy.run_path(str(project_root / "src" / "version.py"))["__version__"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("Expected a major.minor.patch version")
    parts = tuple(map(int, version.split(".")))
    if any(part > 65535 for part in parts):
        raise ValueError("Windows version components must be at most 65535")

    windows_version = parts + (0,)
    file_version = ".".join(map(str, windows_version))
    resource = VSVersionInfo(
        ffi=FixedFileInfo(filevers=windows_version, prodvers=windows_version),
        kids=[
            StringFileInfo([
                StringTable("040904B0", [
                    StringStruct("FileDescription", "Time Series Anomaly Detection"),
                    StringStruct("FileVersion", file_version),
                    StringStruct("InternalName", "TSAnomalyDetector"),
                    StringStruct("OriginalFilename", "TSAnomalyDetector.exe"),
                    StringStruct("ProductName", "Time Series Anomaly Detection"),
                    StringStruct("ProductVersion", version),
                ]),
            ]),
            VarFileInfo([VarStruct("Translation", [1033, 1200])]),
        ],
    )
    path = project_root / "build" / "windows_version_info.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(resource), encoding="utf-8")
    print(f"Generated {path}: File version {file_version}, Product version {version}")


if __name__ == "__main__":
    main()
