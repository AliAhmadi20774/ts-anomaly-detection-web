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

This change stores and validates metadata only: there is no preprocessing
executor, inference endpoint or training operation yet. A declaration is not
proof that the weights match it. Schema 1 does not express legacy section
selection, zero-padding, imputation or custom feature extraction; these need
explicit step definitions before a complete recipe using them can be registered.
Stride and batch size belong to future analysis-run settings, not this field.

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
