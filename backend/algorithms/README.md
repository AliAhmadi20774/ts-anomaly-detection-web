# Model weights

`ModelArtifact` stores a private file reference and its size in bytes, without a
content hash. `ModelVersion.weights` references that artifact. Versions without
weights remain valid metadata records; registering a file does not run or
validate the model's neural-network architecture.

Device names organize folders only; there is no device relationship or extra
device field on model versions. Version numbers remain unique per algorithm.

Register a file for an existing model version:

```powershell
New-Item -ItemType Directory -Force ./models/device1/lstm_ae/v1
if (Test-Path ./models/device1/lstm_ae/v1/weights.bin) { throw "File already exists; choose a new version." }
Copy-Item -LiteralPath ./checkpoint -Destination ./models/device1/lstm_ae/v1/weights.bin
docker compose up -d backend
docker compose exec -T backend python manage.py register_model_weights <model-version-uuid> /app/media/model_weights/device1/lstm_ae/v1/weights.bin --device-folder device1
```

The command copies bytes into private storage without deserializing checkpoints.
Each version gets its own file under
`model_weights/<device-folder>/<algorithm-key>/v<version>/weights.bin`.
For example, `model_weights/device1/lstm_ae/v1/weights.bin`. Choose a distinct
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

Docker Compose bind-mounts the project's `./models` directory at
`/app/media/model_weights`. `MEDIA_ROOT` remains `/app/media`, so database paths
such as `model_weights/device1/lstm_ae/v1/weights.bin` do not change. The host file
is `models/device1/lstm_ae/v1/weights.bin`. See [the storage walkthrough](../../models/README.md).
Local execution without Docker still uses `backend/media` by default; override
`DJANGO_MEDIA_ROOT` to choose its storage root. No public media route or model
API is provided in this step. Back up the database and model folder together.

## Files on other disks or network shares

The source path must be readable by the backend process. In Docker, a host path
or network share must first be mounted into the Linux container; a Windows drive
letter or UNC path alone is not accessible inside it. Registering a mounted
source still copies the file into the configured private storage.

The destination can also be a mounted network filesystem: mount it at
`/app/media/model_weights` instead of the project's `./models` folder (or configure
`DJANGO_MEDIA_ROOT` to its container root). The backend needs read/write permissions. Database file
references stay relative to that storage root. Object storage or direct HTTP
links require a separate Django storage backend; they are not configured here.

If a registered file is unavailable, registration fails with a storage error
instead of silently replacing it. Reconnect its storage or restore its backup.
Database transactions cannot roll back filesystem writes. If a database commit
fails after a file is saved, registration compares and reuses that version's
orphaned file on retry; a different file is rejected.
