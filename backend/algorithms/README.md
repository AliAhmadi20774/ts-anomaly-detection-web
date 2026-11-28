# Model weights

`ModelArtifact` stores a private file reference and its size in bytes, without a
content hash. `ModelVersion.weights` references that artifact. Versions without
weights remain valid metadata records; registering a file does not run or
validate the model's neural-network architecture.

Device names organize folders only; there is no device relationship or extra
device field on model versions. Version numbers remain unique per algorithm.

## Loading registered model weights

The loading path has three parts:

```text
loading.py                       Read the version and its weights from storage
  -> runtimes/registry.py        Choose the loading function by algorithm key
  -> runtimes/lstm_ae.py         Build LSTM-AE and load its trained weights
```

`contracts.py` describes the shared interface; it does not run any loading code.

`algorithms.loading.load_model_version(model_version_id)` reads the registered
version, validates its metadata and opens its file through Django storage. It
copies the stream into a seekable temporary snapshot and checks the registered
byte count before loading. This supports configured storage streams without
requiring a local `file.path`. The check never changes model records or files.

The public return type is `ModelRuntime`, defined in
`algorithms.runtimes.contracts`, rather than an algorithm-specific model class.
This framework-independent loading contract exposes `algorithm_key` and the
ordered `features` tuple. It does not yet define inference operations.
`ModelLoader` describes the common weights-stream and metadata call signature.

`algorithms.runtimes.registry.get_model_loader(algorithm_key)` is the single
place that selects a loading function. Its explicit `match` returns
`load_lstm_ae` for `lstm_ae` and rejects unsupported keys. The function is returned,
not called: `loading.py` calls it after reading and checking the weights file.
Imports stay inside each case, so unused frameworks are not loaded. There is no
mutable registration state, wrapper loader or plugin discovery.

To implement another algorithm:

1. Add its model and loading function in its own `runtimes/` module.
2. Use the `ModelLoader` signature and return a model exposing `algorithm_key`
   and ordered `features`. Validate architecture and weights in that loader.
3. Add a case in `get_model_loader` that imports and returns that function.
4. Test the loader's weights and metadata, including incompatible checkpoints.

The database/storage service stays the same for every algorithm. Code paths are
chosen explicitly in Python, never imported from database module paths.

After dispatch, the service verifies that the runtime satisfies the common
contract and that its algorithm key and feature order match the stored version.
Each algorithm's loader remains responsible for its architecture, weights
format, evaluation configuration and framework-specific details. Tests substitute
a framework-independent example loading function at the selection boundary to
exercise the same database/storage path. This example is not a production
detection algorithm.

```powershell
docker compose exec -T backend python manage.py check_model_weights <model-version-uuid>
```

The algorithm-specific LSTM loader is
`algorithms.runtimes.lstm_ae.load_lstm_ae(source, architecture_params=..., input_spec=...)`.
It uses the pinned PyTorch runtime. It accepts a tensor `state_dict` or
a training checkpoint containing `model_state_dict`; optimizer state, epoch and
loss are not applied. Loading explicitly uses `map_location="cpu"` and
`weights_only=True`, with no unrestricted-pickle fallback. See the official
[PyTorch serialization documentation](https://docs.pytorch.org/docs/2.15/notes/serialization.html).

The supported parameter topology has an encoder LSTM, decoder LSTM and decoder
linear output layer, with checkpoint names `encoder.lstm.*`, `decoder.lstm.*`
and `decoder.linear.*`. Both LSTMs are unidirectional, batch-first and use biases.
`architecture_params` must contain exactly `hidden_size`, `num_layers` and
`dropout`. Hidden size and layer count are positive integers; dropout is in
`[0, 1]`. Input/output feature count comes from `input_spec.features`, preserving
its order. There is no second feature-count field to keep synchronized.

Before constructing the network, the loader checks exact parameter names,
shapes, dense float32 tensor types and finite values. Mismatched hidden sizes,
layer counts or feature counts are rejected rather than partially loaded or
silently cast. Checkpoint validation and initial construction use CPU/float32,
preserving the caller's CPU random state. The loader then transfers the complete
model to the device chosen by `runtimes/torch_device.py`: the first visible CUDA
GPU when `torch.cuda.is_available()` is true, otherwise CPU. Training-only state
is not transferred to GPU. The returned model is in evaluation mode with all
parameter gradients disabled. A transfer error, including GPU memory exhaustion,
is reported rather than silently retrying on CPU.

`model.device` reports the actual parameter device. `model.prepare_inputs(data)`
accepts one preprocessed `[batch, sample, feature]` batch and returns its tensor
on that same device with the same dtype as the model. It validates non-empty
dimensions, feature count and finite values after dtype conversion. Lists,
NumPy arrays and existing tensors are supported, without modifying inputs or
retaining training graphs. Input transfer errors are reported without a device
fallback. This prepares data only; reconstruction and scoring remain separate.

```python
from itertools import islice

# windows comes from iter_preprocessed_windows(...), in model.features order.
window_batch = list(islice(windows, 64))
if window_batch:
    inputs = model.prepare_inputs([window.values for window in window_batch])
    assert inputs.device == model.device
```

Prepare and consume one batch at a time rather than retaining the entire dataset
on GPU. The existing list-based preprocessing remains on CPU; its resulting
model inputs are transferred to GPU before model computation. Reuse
`get_torch_device()` for model loading and `as_numeric_tensor(data)` to read
inputs in future PyTorch algorithms. Validate the algorithm's input shape before
calling `to_model_tensor(inputs, model=...)` to transfer the batch. This rejects
invalid shapes before allocating GPU input memory. Input transfer follows the actual
model parameters instead of independently choosing a device a second time. No
hardware choice is saved in model metadata, and the same weights file can be
used on CPU development machines and CUDA servers.

See [the deployment instructions](../README.md#cpu-and-gpu-deployment) for the
CUDA build and Docker device access. The selection follows the official
[PyTorch device-agnostic example](https://docs.pytorch.org/docs/2.15/notes/cuda.html#device-agnostic-code).

The declared dropout setting is retained in `model.architecture`. Effective
dropout is zero for one layer because LSTM dropout applies between stacked
layers; see [PyTorch LSTM](https://docs.pytorch.org/docs/2.15/generated/torch.nn.LSTM.html).
Tensor dimensions cannot prove the training dropout or preprocessing recipe.
Those declarations still need to match external training.

## LSTM-AE reconstruction and scoring

`model.predict(data, reconstruction_repeats=10)` executes one preprocessed input
batch. The argument is a positive integer (booleans are rejected). Set it to 1
for one reconstruction, or another count for averaging. It is an execution
option in code, not a database field or architecture parameter. The returned
`ReconstructionResult` records the count actually used, together with:

- `reconstruction`: the averaged `[batch, sample, feature]` tensor.
- `scores`: one MSE value per window, shape `[batch]`.

```python
result = model.predict(window_values, reconstruction_repeats=5)
print(result.reconstruction.shape, result.scores.shape)
print(result.reconstruction_repeats)  # 5
```

`forward(inputs)` performs one reconstruction using prepared tensors. Encoder
hidden and cell states are sampled from a standard normal distribution on the
input device and dtype for each call. Its final states initialize the decoder.
Starting with the last observed sample, the decoder feeds its own predictions
back and writes reconstructed samples from end to beginning. States stay local
to the call and do not persist across independent batches. This reproduces the
previous runtime's decoding policy without importing legacy project code.
The original training loop is not present in this repository; this compatibility
is verified against the earlier inference implementation, not a training recipe.

`predict` prepares input on the model device and calls the shared
`torch_inference.reconstruct_batch` runner. The runner puts the model in evaluation
mode and leaves it there. Both input preparation and execution run under
[PyTorch inference mode](https://docs.pytorch.org/docs/2.15/generated/torch.autograd.grad_mode.inference_mode.html).
Dropout is disabled, but explicit random initial states remain random. Callers
control seeds outside the runtime; changing batch layout or CPU/CUDA backend can
change sampled states and floating-point results.

Outputs are accumulated one at a time, with memory independent of the repeat
count. The mean is computed before scoring:
`scores = ((inputs - reconstruction) ** 2).mean(dim=(1, 2))`.
This is MSE of the mean reconstruction, not the mean of separate MSE scores.
Incremental accumulation can differ slightly from stacked averaging due to
floating-point rounding. Unexpected output shapes/devices/dtypes, non-finite
reconstructions and MSE overflow are rejected. Inputs, weights, reconstruction
and scores stay on the same device; no per-step CPU copies are made.

Prepare and consume batches one at a time. This batch-level runtime does not
read raw signal files, choose preprocessing, apply thresholds, classify windows
or save analysis records. Model loading still does not execute predictions.
An unconfigured preprocessing profile remains unchanged: weight loading and a
supplied preprocessed batch do not establish the correct raw-data training recipe.

`check_model_weights` reports missing versions, unavailable files, byte-count
mismatches and incompatible checkpoints. Its output uses the common runtime
identity without inspecting LSTM architecture attributes. This standalone
diagnostic command is temporary and will be removed after an analysis entry point
provides the required checks. Only `lstm_ae` currently has a production
loader; other algorithms fail explicitly until their loaders are registered.

## Analyzing a stored test

`algorithms.inference.analyze_test` is the permanent backend service connecting
stored signals, preprocessing, model loading and batched inference:

```python
from algorithms.inference import analyze_test

result = analyze_test(
    test_run_id, model_version_id,
    stride=25, batch_size=100, reconstruction_repeats=10,
    start_sample=0, end_sample=1000,
)
for window in result.windows:
    print(window.start_time_s, window.end_time_s, window.score)
```

The caller explicitly selects the test and model. Signals must match
`input_spec.features` by exact name and are placed in that order. Missing,
empty, unequal-length or non-finite selected signals are rejected. There are
no inferred aliases, signal substitutions or zero padding. The service uses the
sample rate saved on `TestRun`; later edits to its definition do not change it.
It uses one model metadata snapshot for both preprocessing and weight loading.
`loading.load_model(version)` loads that already-read snapshot;
`loading.load_model_version(id)` remains the ordinary ID-based loading entry.

`stride` is required and counts processed samples. Optional `start_sample` and
exclusive `end_sample` select a range in original samples; omission analyzes
the entire measured signal. Call separately for sections to avoid crossing
their boundaries. Out-of-range selections and ranges without a complete model
window are rejected. Result bounds are half-open original sample indices and
relative seconds, including when resampling is configured.

The runtime must implement `ReconstructionRuntime.predict`; the smaller
`ModelRuntime` contract remains sufficient for loading-only algorithms.
Currently LSTM-AE implements reconstruction-based analysis. The model is loaded
once, batches execute on its device, and scalar scores are copied to CPU once
per batch. `AnalysisResult` records IDs, ordered features, source rate, stride,
batch size, repeat count and immutable window scores. Source arrays and returned
scores still occupy CPU memory; batching bounds inference tensor memory.

This service does not create records, apply thresholds or expose an HTTP/UI
entry. Its tests exercise the full database/storage/LSTM path on a disposable
database. The development model uses `current_a` (current in amperes), matching
the existing synthetic `test1` traces. These already contain 22,528 samples at
1 kHz, matching the old signal length without padding or truncation. This demo
mapping tests the software path; it does not establish training compatibility
or a calibrated current-anomaly threshold.

The inference service and its tests are permanent application code.
`check_model_weights` is a temporary independent loading diagnostic;
`register_model_weights` remains a weight-registration tool. The two
`sample_data.generate_sample_*` modules generate test fixtures and are not part
of production inference. No automatic legacy transfer scripts are required.

## Preprocessing metadata

`ModelVersion.preprocessing` is an optional, validated JSON declaration. SQL
`NULL` means **not configured**, independently of an explicit normalization
method of `none`. Existing versions remain unconfigured after migration 0009;
no training settings are inferred from the legacy inference code.

Example declaration (illustrative, not an installed legacy training recipe):

```json
{
  "schema_version": 1,
  "steps": [
    {"type": "resample", "method": "mean"},
    {"type": "normalize", "method": "none"},
    {"type": "window", "size": 50, "tail": "drop"}
  ]
}
```

Schema 1 accepts these explicit step declarations:

- `resample`: `method` is `mean`, `min` or `max`. The target sampling rate comes
  from `input_spec.sample_rate_hz`; do not duplicate it in the step. Resampling
  must precede windowing.
- `normalize`: `method` is `none`, `standardize` or `minmax`. `none` has no fitted
  parameters. `standardize` requires fitted `mean` and strictly positive `scale`
  vectors, defining `(x - mean) / scale`. `minmax` requires fitted non-negative
  `scale` and finite `offset` vectors, defining `x * scale + offset`, plus an
  increasing two-number target `range` and explicit boolean `clip`. If clipping
  is enabled, clip the transformed values to that range. These parameters come
  from external training; this step never fits a scaler on new measurements.
- `window`: a positive integer `size` and explicit `tail` policy, `drop` or
  `reject`. `drop` excludes incomplete windows; `reject` declares that incomplete
  windows must produce an error. There can be at most one windowing step.

The ordered `steps` list preserves operation order, including normalization
before or after windowing. Fitted vectors must contain one value per feature in
`input_spec.features` order. Unknown keys, unknown versions/steps, non-finite
numbers and invalid parameters are rejected. Call `full_clean()` before saving
metadata (the weight-registration service already does this). The database also
rejects non-object JSON values; it allows SQL `NULL` for unconfigured versions.

The metadata validator only checks declarations. The executor below supports
resampling, normalization and windowing; there is no inference endpoint or
training operation yet. A declaration is not proof that the weights match it.
Schema 1 does not express legacy section
selection, zero-padding, imputation or custom feature extraction; these need
explicit step definitions before a complete recipe using them can be registered.
Stride and batch size belong to future analysis-run settings, not this field.

## Normalization primitive

`algorithms.normalization.normalize_samples` executes one stored `normalize`
step on `[sample, feature]` rows. It is independent of Django, legacy code and
model frameworks. Parameters must come from external training, in the same
column order as `input_spec.features`; the function never fits a scaler.

```python
from algorithms.normalization import normalize_samples

step = {
    "type": "normalize", "method": "standardize",
    "mean": [10, 100], "scale": [2, 20],
}
normalized = normalize_samples([[8, 60], [14, 120]], step=step)
# ((-1.0, -2.0), (2.0, 1.0))
```

`none` preserves values. `standardize` uses `(x - mean) / scale`; `minmax` uses
`x * scale + offset` with optional clipping to the stored range. Without
clipping, values outside the training range remain outside the target range.
The result contains immutable float rows; inputs and parameters are unchanged.
Invalid samples, feature-count mismatches and arithmetic overflow are rejected.
Overflow is checked before clipping so clipping cannot hide invalid arithmetic.
Empty input returns an empty tuple after validating the normalization step.

Metadata validation and execution share `validate_normalization`, ensuring that
both accept the same fitted parameter format. Sample validation is shared with
windowing in the private `_samples` module. Normalization can be called before
windowing or on each window's values; it does not change sample bounds.

## Preprocessing executor

`algorithms.preprocessing.iter_preprocessed_windows` executes the stored steps
in order. It requires exactly one `window` step and supports any declared
`normalize` steps before or after it. `resample` steps execute before windowing,
in their declared order relative to normalization. Valid metadata without a window can still
be saved, but this window-producing executor rejects it. An unconfigured `None`
profile also fails explicitly. Resampling requires the actual input rate in
`source_sample_rate_hz`; its target comes from `input_spec.sample_rate_hz`.
An invalid or unsupported rate fails before measurements are consumed.

```python
from algorithms.preprocessing import iter_preprocessed_windows

profile = {
    "schema_version": 1,
    "steps": [
        {"type": "normalize", "method": "standardize", "mean": [10], "scale": [2]},
        {"type": "window", "size": 2, "tail": "reject"},
    ],
}
windows = list(iter_preprocessed_windows(
    [[10], [14], [18]], preprocessing=profile,
    input_spec={"features": ["current_a"]}, stride=1, offset=100,
))
# [100, 102): ((0.0,), (2.0,))
# [101, 103): ((2.0,), (4.0,))
```

For a stored version, pass `preprocessing=model_version.preprocessing` and
`input_spec=model_version.input_spec`. Stride remains a runtime analysis setting.
No weights are loaded and no database query is made by this function.

The executor validates the entire declaration, input specification and fitted
vector lengths using the same rules as the Django metadata validators. These
rules live in the framework-independent `_specs` module; the Django classes keep
their existing migration-compatible paths and report Django `ValidationError`.
The executor itself uses `ValueError` for invalid input.

Samples are validated and copied before returning an iterator; all measurements
must be finite, including any dropped tail. Actual column counts must match
`input_spec.features`, but callers supply the correct feature order and actual
sampling rate because numeric rows alone cannot identify them. Without a
resampling step, a supplied source rate must match the declared model rate.
Pass each serial or section separately. Window size and stride count processed
samples; returned bounds and offsets always use the ORIGINAL input sample domain.
Divide bounds by the source rate to locate the contributing data in seconds.
After resampling, `window.end - window.start` may differ from the number of rows
in `window.values`.

Settings are also copied so later caller changes cannot affect execution.
Pre-window normalization is eager. Windows and post-window normalization are
lazy, avoiding a complete materialized array of overlapping windows. Arithmetic
errors after windowing surface during iteration and include the affected window
bounds; callers must consume the iterator to complete preprocessing. Empty input
returns no windows after configuration validation. Outputs remain immutable
`SampleWindow` objects; model-specific batching and tensor conversion are not
part of this step.

## Resampling primitive

`algorithms.resampling.resample_samples` aggregates `[sample, feature]` rows
using `mean`, `min` or `max`, independently for each feature. It supports equal
rates and downsampling, including fractional ratios. Upsampling is rejected
because these aggregation methods do not define an interpolation policy.

```python
from algorithms.resampling import resample_samples

series = resample_samples(
    [[2], [4], [10], [14], [20]], source_sample_rate_hz=1000,
    target_sample_rate_hz=500, method="mean",
)
# series.values:        ((3.0,), (12.0,), (20.0,))
# series.source_bounds: ((0, 2), (2, 4), (4, 5))
```

Sample i has time `i / source_rate`; bin k is left-closed and right-open,
`[k / target_rate, (k + 1) / target_rate)`, anchored at the supplied series start.
Decimal rates use exact rational boundaries to avoid accumulated rounding drift.
Only bins through the last sample's timestamp are produced. A final partial bin
uses its available measurements, with no padding. Window tail policy is applied
later to the resulting rows and is independent of this partial-bin behavior.
No additional filtering is applied; use the aggregation method and rates that
match the model's external training recipe.

The immutable `ResampledSeries` contains values, contributing `source_bounds`,
the original `source_sample_rate_hz` and output `sample_rate_hz`. Bounds partition
the supplied input without gaps or duplication. For fractional ratios, these
bounds describe the actual contributing samples rather than the nominal bin
edges. Normalization never changes this mapping. The executor also composes
mappings for repeated resampling steps and preserves bounds through lazy
post-window normalization.

Example execution of a stored recipe:

```python
profile = {
    "schema_version": 1,
    "steps": [
        {"type": "resample", "method": "mean"},
        {"type": "window", "size": 2, "tail": "reject"},
    ],
}
windows = list(iter_preprocessed_windows(
    [[2], [4], [10], [14]], preprocessing=profile,
    input_spec={"features": ["current_a"], "sample_rate_hz": 500},
    source_sample_rate_hz=1000, stride=1, offset=100,
))
# One window: values ((3.0,), (12.0,)), original bounds [100, 104).
# Its contributing source interval is [0.100, 0.104) seconds.
```

## Windowing primitive

`algorithms.windowing.iter_windows` is a standalone, standard-library-only
function. It has no Django, legacy-code, NumPy or model-framework dependency.
Pass one time series as rows in `[sample, feature]` order; the caller is
responsible for feature selection and order. For a scalar signal, wrap each value
in a one-element row. Different serials or sections require separate calls.

```python
from algorithms.windowing import iter_windows

windows = list(iter_windows(
    [[value] for value in range(1000)],
    window_size=50, stride=25, tail="drop", offset=0,
))
# 39 windows: [0, 50), [25, 75), ..., [950, 1000)
# windows[0].values contains 50 rows, each with one feature.
```

Each immutable `SampleWindow` has `start`, exclusive `end` and `values`.
Bounds refer to the supplied sample index domain plus `offset`; the function
does not map resampled indices back to raw timestamps. Pass a section's sample
offset when its indices should be absolute within the same sample domain.

Input is validated and snapshotted once before the iterator is returned.
Overlapping windows reuse immutable feature rows without altering source data.
The window iterator avoids materializing all windows at once. Values are finite
Python floats; empty/ragged feature rows, nonnumeric values and non-finite
numbers are rejected. Window size and stride must be positive integers.

With `drop`, incomplete end data is excluded without padding. With `reject`,
non-empty input must have at least one full window and its last complete window
must reach the end; stride gaps between windows remain intentional. Empty input
yields no windows for either policy. No section boundaries, sampling frequency,
normalization or architecture assumptions are embedded in this function.

Register a file for an existing model version:

```powershell
New-Item -ItemType Directory -Force ./backend/models/device1/lstm_ae/v1
if (Test-Path ./backend/models/device1/lstm_ae/v1/weights.bin) { throw "File already exists; choose a new version." }
Copy-Item -LiteralPath ./checkpoint -Destination ./backend/models/device1/lstm_ae/v1/weights.bin
docker compose up -d backend
docker compose exec -T backend python manage.py register_model_weights <model-version-uuid> /app/models/device1/lstm_ae/v1/weights.bin --device-folder device1
```

The command copies bytes into private storage without deserializing checkpoints.
Each version gets its own file under
`<device-folder>/<algorithm-key>/v<version>/weights.bin` relative to the models root.
For example, `device1/lstm_ae/v1/weights.bin`. Choose a distinct
folder for each device; the folder does not need to exist in the device table.
Folder names accept 1-64 letters, digits, underscores or hyphens, without path
separators. `--device-folder` is required for new files; it can be omitted when
checking an existing registration. Supplying another location does not move or
replace an existing registered file.
Repeating registration compares the stored bytes directly to the supplied file;
different weights require a new model version. Files are not deduplicated across
versions. There is no stored checksum or background integrity verification.
Existing file paths are preserved when migrating away from hashes.

Migration 0007 removes the device relationship introduced by 0005/0006 and
restores uniqueness per algorithm. It preserves model metadata and file records;
conflicting version numbers must be resolved before applying it. Database
migrations do not move stored files; an existing file path can be changed after
copying and verifying its bytes in the new directory.

Docker Compose bind-mounts the project's `./backend/models` directory at `/app/models`.
`MEDIA_ROOT` points to `/app/models`, so database paths such as
`device1/lstm_ae/v1/weights.bin` match the layout within the local models folder.
The host file is `backend/models/device1/lstm_ae/v1/weights.bin` and the container file is
`/app/models/device1/lstm_ae/v1/weights.bin`. See [the storage walkthrough](../models/README.md).
Local execution without Docker also uses the backend's `models` directory by
default; override `DJANGO_MEDIA_ROOT` to choose its storage root. No public media route or model
API is provided in this step. Back up the database and model folder together.
Migration 0008 updates old `model_weights/` references to this root without
moving files or adding database relationships.

## Files on other disks or network shares

The source path must be readable by the backend process. In Docker, a host path
or network share must first be mounted into the Linux container; a Windows drive
letter or UNC path alone is not accessible inside it. Registering a mounted
source still copies the file into the configured private storage.

The destination can also be a mounted network filesystem: mount it at
`/app/models` instead of the project's `./backend/models` folder (or configure
`DJANGO_MEDIA_ROOT` to its container root). The backend needs read/write permissions. Database file
references stay relative to that storage root. Object storage or direct HTTP
links require a separate Django storage backend; they are not configured here.

If a registered file is unavailable, registration fails with a storage error
instead of silently replacing it. Reconnect its storage or restore its backup.
Database transactions cannot roll back filesystem writes. If a database commit
fails after a file is saved, registration compares and reuses that version's
orphaned file on retry; a different file is rejected.
