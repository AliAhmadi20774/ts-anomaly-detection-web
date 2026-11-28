# Backend development

## CPU and GPU deployment

Model loaders automatically prefer the first visible CUDA GPU and otherwise use
CPU. The default Docker build installs CPU PyTorch for development:

```powershell
docker compose up -d --build backend
```

On an NVIDIA GPU server, use the additional Compose file. It builds CUDA PyTorch
and requests one GPU for the backend. Its `:cuda` image tag keeps the GPU build
separate from the default CPU image:

```powershell
docker compose -f compose.yaml -f compose.gpu.yaml up -d --build backend
```

The server needs a compatible NVIDIA GPU/driver and Docker GPU support. Follow
the [Docker GPU prerequisites](https://docs.docker.com/compose/how-tos/gpu-support/)
or [Docker Desktop GPU setup](https://docs.docker.com/desktop/features/gpu/) for
the host platform. The GPU overlay explicitly requires GPU access; use the base
Compose file on CPU hosts. Application-level CPU fallback applies after the
container starts, when PyTorch cannot see an available CUDA device.

Both builds use PyTorch 2.15.0. The Dockerfile defaults `TORCH_INDEX_URL` to the
official CPU wheel index. The GPU overlay defaults it to the official `cu132`
index; override the build variable when deploying another supported CUDA wheel
variant for the same PyTorch version. Changing a wheel index requires rebuilding
the image. No GPU driver or CUDA toolkit is installed on the development host by
these project changes.

Check the deployed build and device:

```powershell
docker compose -f compose.yaml -f compose.gpu.yaml exec -T backend python -c "import torch; from algorithms.runtimes.torch_device import get_torch_device; print(torch.__version__, torch.version.cuda, get_torch_device())"
```

To install the CPU build in a local virtual environment, from `backend/`:

```powershell
python -m pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
```

Both model placement and input transfer are implemented. For LSTM-AE, use
`model.prepare_inputs(data)` for each preprocessed `[batch, sample, feature]`
batch. The returned tensor matches the model's actual device and dtype. Parsing
and list-based preprocessing remain CPU work; model inputs are transferred to
GPU when the model is on GPU. `model.predict(data, reconstruction_repeats=10)`
returns mean reconstruction and per-window MSE on that same device. The repeat
count is a positive integer execution argument and is included in the returned
result; no analysis results are persisted to the database yet. See
[reconstruction and scoring](algorithms/README.md#lstm-ae-reconstruction-and-scoring)
for the stochastic decoding policy and batch-level runtime boundary.

## Tests

Each app keeps its tests in a `tests/` Python package, next to the code it covers.
Files use `test_<subject>.py` names. Keep `tests/__init__.py` empty so importing
the package does not load unrelated tests or require database configuration.

```text
backend/
  accounts/tests/
  algorithms/tests/
    test_algorithms.py
    test_artifacts.py
    test_lstm_inference.py
    test_lstm_inputs.py
    test_lstm_loading.py
    test_model_loading.py
    test_model_versions.py
    test_models_root_migration.py
    test_normalization.py
    test_preprocessing.py
    test_preprocessing_metadata.py
    test_resampling.py
    test_runtime_registry.py
    test_storage_only_migration.py
    test_torch_device.py
    test_windowing.py
  dat_imports/tests/
  devices/tests/
  health/tests/
  sample_data/tests/
```

The algorithm primitive and preprocessing executor tests use standard-library `unittest` and need no
Django settings or database. From `backend/`, with the project's Python
environment active:

```powershell
python -m unittest algorithms.tests.test_normalization algorithms.tests.test_windowing algorithms.tests.test_preprocessing algorithms.tests.test_resampling -v
```

The standalone LSTM weight-loader tests require PyTorch/NumPy from
`requirements.txt`, but no Django settings or database:

```powershell
python -m unittest algorithms.tests.test_lstm_loading -v
```

`test_torch_device.py` checks CUDA preference and CPU fallback without needing
a GPU. Loader tests check dispatch and transfer errors on CPU test hosts. The
CUDA integration test in `test_lstm_loading.py` checks exact weights, input
transfer from CPU data and actual LSTM/linear CUDA execution when a working GPU
is available; it is skipped on CPU hosts. `test_lstm_inputs.py` checks the path
from preprocessed windows to model inputs, shapes, values, dtype, invalid data
and transfer errors. `test_lstm_inference.py` covers recorded reference outputs,
reverse feedback decoding, configurable repeat counts, MSE of the averaged
reconstruction, inference mode and invalid outputs. The CUDA integration test
also executes `predict`, checking reconstruction and score tensors on GPU. Run
the suite on a GPU server to complete hardware verification.

`test_model_loading.py` covers database metadata, private storage and the
`check_model_weights` management command as part of the complete Django suite.
It also exercises a second example algorithm through the same loading service.
`test_inference.py` covers stored signal selection, preprocessing, source-time
bounds, batching, failure validation and the full registered LSTM-to-score path.
`test_runtime_registry.py` checks explicit loader selection, the shared interface
and lazy framework imports. Its LSTM selection check requires PyTorch but no
Django settings or database.

For the complete suite, configure `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER` and
`PGPASSWORD` for a disposable PostgreSQL instance, then run from `backend/`:

```powershell
python manage.py test --noinput
```

The test role must be allowed to create the temporary test database. Do not
grant extra privileges to the application's normal database role. Django
discovers the app test packages and `sample_data/tests/` automatically when run
from this directory. A specific app can be selected with a label such as
`python manage.py test algorithms.tests --noinput`.

Tests requiring models or APIs use Django/DRF test cases. Migration tests use
transactional test cases and restore the latest schema during cleanup. Shared
test helpers should live inside the relevant `tests/` package rather than in
production modules or package initialization files.
