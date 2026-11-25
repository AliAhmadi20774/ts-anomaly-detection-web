# Model weights

`ModelArtifact` stores a private file reference, its size in bytes and its SHA256.
`ModelVersion.weights` references that artifact. Versions without weights remain
valid metadata records; registering a file does not run or validate the model's
neural-network architecture.

Register a file for an existing model version:

```powershell
docker compose cp ./checkpoint backend:/tmp/checkpoint
docker compose exec -T backend python manage.py register_model_weights <model-version-uuid> /tmp/checkpoint
```

The command copies bytes into private storage without deserializing checkpoints.
Identical files share an artifact. Repeating a registration verifies the stored
bytes; different weights require a new model version. A missing stored file can
be restored from matching source bytes. A corrupt stored file is rejected.

Docker Compose persists the files in the `model_artifacts` named volume mounted
at `/app/media`. Local execution uses `backend/media` by default; override it with
`DJANGO_MEDIA_ROOT`. No public media route or model API is provided in this step.
Back up the database and the artifact volume together.

Database transactions cannot roll back filesystem writes. If a database commit
fails after a file is saved, registration can verify and reuse that file on retry.
