# Time-Series Anomaly Detection

A deep learning-based anomaly detection system for time-series data using LSTM Autoencoders.

## Features

- **LSTM Autoencoder Model**: Encoder-decoder architecture for time-series reconstruction
- **Multi-section Analysis**: Configurable sections for different signal regions
- **Parallel Data Loading**: Multi-threaded loading of compressed `.dat` files
- **GUI Application**: User-friendly interface for running anomaly detection
- **Batch Mode**: Execute all tests for a device with a single click
- **Visual Reports**: Always generates interactive HTML reports and a dashboard; PNG plots and PDF reports are available as additional outputs.
- **Empty Signal Handling**: Tests with an empty signal are excluded from model evaluation and shown as No Data in HTML dashboards and detail reports, separately from Normal/Anomaly results.
- **Missing Tests**: Batch reports list every expected test. A serial with a missing test is marked Incomplete unless an evaluated test already has an anomaly; missing tests are shown in the dashboard and report tabs.
- **Flexible Configuration**: Supports multiple devices and test configurations

## Project Structure

```
ts-anomaly-detection/
├── src/
│   ├── config/
│   │   └── global_config.py       # Device, test, and section configurations
│   ├── data/
│   │   ├── loader.py              # Parallel loading of .dat files
│   │   └── airbus_dataset.py      # PyTorch Dataset
│   ├── gui/
│   │   └── app.py                 # Graphical user interface
│   ├── inference/
│   │   └── model_inference.py     # Model inference and prediction
│   ├── models/
│   │   ├── lstm_autoencoder.py    # LSTM Autoencoder model definition
│   │   └── management.py          # Model checkpoint management
│   ├── pipeline/
│   │   └── runner.py              # Complete pipeline execution
│   ├── processing/
│   │   └── signal.py              # Signal preprocessing and windowing
│   └── visualization/
│       └── plots.py               # Plot generation
├── checkpoints/                   # Trained models
│   └── device1/
│       └── lstm_ae_epoch_1
├── proto/
│   ├── schema.proto               # Protocol Buffer schema
│   └── generated/
│       └── schema_pb2.py          # Generated protobuf code
├── scripts/                       # Helper scripts
│   ├── create_dat_file.py
│   └── create_sample_folder.py
├── data/
│   ├── sample_dat_files/          # Sample data files
│   └── raw/                       # Raw input data
├── tests/                         # Unit tests
│   ├── test_loader.py
│   ├── test_processing.py
│   └── test_inference.py
├── outputs/                       # Runtime outputs (.gitignore)
│   ├── single/                    # Single test runs
│   └── batch/                     # Batch runs
├── main.py                        # Main entry point
├── requirements.txt               # Python dependencies
└── README.md
```

## Requirements

- Python 3.13 (recommended for the bundled offline wheels)
- Windows 64-bit if you want to use the wheels inside `packages/`
- `tkinter` for the GUI

Main Python packages used by the project:

- `torch`
- `numpy`
- `pandas`
- `matplotlib`
- `protobuf`
- `grpcio-tools`
- `tqdm`
- `plotly`
- `reportlab`

Optional for running tests:

- `pytest`

## Installation

For building a Windows executable, see [the EXE build guide](README_EXE.md).

### Option A: Online install

1. Clone the repository:
```bash
git clone https://github.com/AliAhmadi20774/ts-anomaly-detection.git
cd ts-anomaly-detection
```

2. Create and activate virtual environment:
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
```

3. Install dependencies:
```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If `pip` prints `Could not find a version that satisfies the requirement ...`, check these first:

- Your Python version. The bundled wheels in this repository are for `Python 3.13`.
- Your platform. The bundled wheels are `win_amd64`, so they are for 64-bit Windows.
- Your internet connection, if you are using online installation.

### Option B: Offline install from `packages/`

The `packages/` folder is a local wheel cache. Use it with `pip --find-links`, not by installing each wheel one by one.

```powershell
python -m pip install --no-index --find-links .\packages -r requirements.txt
```

Important limitations:

- The current `packages/` folder only contains wheels for `Windows + Python 3.13`.
- The current `packages/` folder is not a guaranteed full offline mirror of every transitive dependency.
- If a package is still reported as missing during offline install, add its wheel to `packages/` first, then run the command again.

To build a complete offline cache on a machine that has internet access:

```powershell
python -m pip download -r requirements.txt -d .\packages
```

If you want to force the project virtual environment explicitly on Windows, replace `python` with `.\.venv\Scripts\python.exe`.

## Quick Start

### 1. Run the GUI Application

```bash
python main.py
```

### 2. Select Data

- Click **Browse** and select the folder containing `.dat` files
- Choose a device (e.g., `device1`)
- Select one of two modes:

#### Single Test Mode
- Select a specific test (e.g., `test1`)
- Click **Start**

#### Batch Mode
- Check **Run all tests for selected device**
- Click **Start** (all tests for the device will run)

### 3. View Outputs

Outputs are saved in the `outputs/` folder:

```
outputs/
├── single/
│   └── device1/
│       └── test1/
│           └── 20260630_150000/
│               ├── 01_section_01/
│               │   ├── 0/          # Negative (normal) samples
│               │   └── 1/          # Positive (anomaly) samples
│               └── errors.txt      # Detected anomalies list
│
└── batch/
    └── device1/
        └── 20260630_150000/
            ├── test1/
            │   ├── sections...
            │   └── errors.txt
            └── test2/
                ├── sections...
                └── errors.txt
```

## Configuration

### Application Version

The version is defined in `src/version.py` using `major.minor.patch` format (currently `0.1.0`) and appears in the window title. The [EXE build instructions](README_EXE.md) use the same version for Windows file properties, with a fourth numeric component of `0`.

### Device and Test Configuration

Edit `src/config/global_config.py` to configure:

### Device to Test Mapping
```python
DEVICE_TEST_MAPPING = {
    "device1": ["test1", "test2"],
    "device2": ["test5", "test6"],
    # ...
}
```

### Section Parameters
```python
CONFIG["device1"]["test1"]["sections"] = {
    "01_section_01": {
        "start": 0,
        "end": 1000,
        "batch_size": 100,
        "step_window": 25,
        "size_window": 50,
        "resample_freq": "1",
        "hidden_size": 300,
        "num_layers": 1,
        "dropout": 0.2,
        "model_path": "checkpoints/device1/lstm_ae_epoch_1",
        "threshold1": 0.35,
        "threshold2": 0.36,
        "transfo": ["mean"],
    },
    # ...
}
```

### Configurable Parameters per Section

| Parameter | Description | Example |
|-----------|-------------|---------|
| `start`, `end` | Signal slice boundaries | `0`, `1000` |
| `batch_size` | Batch size for inference | `100` |
| `step_window` | Step size for sliding window | `25` |
| `size_window` | Window size | `50` |
| `resample_freq` | Resampling frequency (ms) | `"1"` |
| `hidden_size` | LSTM hidden units | `300` |
| `num_layers` | Number of LSTM layers | `1` |
| `dropout` | Dropout rate | `0.2` |
| `model_path` | Path to trained model | `checkpoints/device1/...` |
| `threshold1` | Normal/Warning threshold | `0.35` |
| `threshold2` | Warning/Anomaly threshold | `0.36` |
| `transfo` | Preprocessing transformations | `["mean"]` |

## Input Data Format

The system expects `.dat` files (gzip compressed) containing:

- `Array_ProtoDevice`: Root protobuf message
- `items`: Repeated field of `ProtoDevice`
- Current loader behavior: reads `items[0]`, so each file should contain exactly one `ProtoDevice`
- `ProtoDevice.deviceSeries`: Device identifier
- `ProtoDevice.serialNumber`: Unique serial number
- `ProtoDevice.testResult`: List of test results with signals
- `ProtoTestResult.testName`: Test identifier such as `test1` or `test2`
- `ProtoSignal.name`: Signal name, expected to be `signal1` or `Signal1`
- `ProtoSignal.data`: Signal samples stored as `double`

The canonical protobuf definition is `proto/schema.proto`.

### Generating Sample Data

To create sample `.dat` files:

```bash
cd data
set PYTHONPATH=..
..\.venv\Scripts\python.exe ..\scripts\create_sample_folder.py
```

This script creates 10 sample files in `data/sample_dat_files/`.

## Anomaly Detection Process

1. **Data Loading**: Parallel loading of `.dat` files filtered by device/test
2. **Preprocessing**: Windowing, transformations (mean, max, min), and resampling
3. **Inference**: Model predicts reconstruction with 10 forward passes averaged
4. **Scoring**: MSE between input and reconstruction
5. **Classification**:
   - `< threshold1`: Normal (white)
   - `threshold1 - threshold2`: Warning (yellow)
   - `> threshold2`: Anomaly (red)

## Model Architecture

The LSTM Autoencoder consists of:

- **Encoder**: LSTM network converting input to latent representation
- **Decoder**: LSTM network reconstructing sequence from latent space

Based on: ["LSTM-based Auto-encoder for Anomaly Detection"](https://arxiv.org/pdf/1607.00148.pdf)

## Running Tests

Execute unit tests:

```bash
pytest tests/
```

The alignment regression tests in `tests/test_window_alignment.py` use synthetic
`.dat` files with spikes at known sample positions. They check preprocessing,
reconstruction error, saved report coordinates, and Plotly rectangles with
resampling periods of 1, 2, 2.5, and 5 ms. A deterministic reference model isolates
coordinate alignment from the trained model's accuracy.
The highlighting tests also verify that healthy parts of a section remain
unshaded; only warning and error windows receive colored bands.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Author

Ali Ahmadi

## Contributing

For bug reports or feature requests, please use GitHub Issues.
