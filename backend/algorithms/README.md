# Model weights

`ModelArtifact` stores a private file reference and its size in bytes, without a
content hash. `ModelVersion.weights` references that artifact. Versions without
weights remain valid metadata records; registering a file does not run or
validate the model's neural-network architecture.

Device names organize folders only; there is no device relationship or extra
device field on model versions. Version numbers remain unique per algorithm.

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
normalization and windowing; there is no inference endpoint or training operation
yet. A declaration is not proof that the weights match it. Schema 1 does not express legacy section
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
`normalize` steps before or after it. Valid metadata without a window can still
be saved, but this window-producing executor rejects it. An unconfigured `None`
profile also fails explicitly. A declared `resample` step raises
`NotImplementedError` before measurements are consumed; it is never skipped.

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
    input_spec={"features": ["signal1"]}, stride=1, offset=100,
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
`input_spec.features`, but callers supply the correct feature order and sampling
rate because numeric rows alone cannot identify them. Pass each serial or
section separately; offsets refer to the supplied sample index domain.

Settings are also copied so later caller changes cannot affect execution.
Pre-window normalization is eager. Windows and post-window normalization are
lazy, avoiding a complete materialized array of overlapping windows. Arithmetic
errors after windowing surface during iteration and include the affected window
bounds; callers must consume the iterator to complete preprocessing. Empty input
returns no windows after configuration validation. Outputs remain immutable
`SampleWindow` objects; model-specific batching and tensor conversion are not
part of this step.

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
