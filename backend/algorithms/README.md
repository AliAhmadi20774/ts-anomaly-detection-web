# Model weights

`ModelArtifact` stores a private file reference and its size in bytes, without a
content hash. `ModelVersion.weights` references that artifact. Versions without
weights remain valid metadata records; registering a file does not run or
validate the model's neural-network architecture.

Register a file for an existing model version:

```powershell
docker compose cp ./checkpoint backend:/tmp/checkpoint
docker compose exec -T backend python manage.py register_model_weights <model-version-uuid> /tmp/checkpoint
```

The command copies bytes into private storage without deserializing checkpoints.
Each version gets its own file under `model_weights/<version-uuid>/weights.bin`.
Repeating registration compares the stored bytes directly to the supplied file;
different weights require a new model version. Files are not deduplicated across
versions. There is no stored checksum or background integrity verification.
Existing file paths are preserved when migrating away from hashes.

Docker Compose persists the files in the `model_artifacts` named volume mounted
at `/app/media`. Local execution uses `backend/media` by default; override it with
`DJANGO_MEDIA_ROOT`. No public media route or model API is provided in this step.
Back up the database and the artifact volume together.

## Files on other disks or network shares

The source path must be readable by the backend process. In Docker, a host path
or network share must first be mounted into the Linux container; a Windows drive
letter or UNC path alone is not accessible inside it. Registering a mounted
source still copies the file into the configured private storage.

The destination can also be a mounted network filesystem: mount it at
`/app/media` instead of the default named volume (or configure `DJANGO_MEDIA_ROOT`
to its container path). The backend needs read/write permissions. Database file
references stay relative to that storage root. Object storage or direct HTTP
links require a separate Django storage backend; they are not configured here.

If a registered file is unavailable, registration fails with a storage error
instead of silently replacing it. Reconnect its storage or restore its backup.
Database transactions cannot roll back filesystem writes. If a database commit
fails after a file is saved, registration compares and reuses that version's
orphaned file on retry; a different file is rejected.
