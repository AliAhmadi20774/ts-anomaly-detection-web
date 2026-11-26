# Local model files and Docker

The project's `backend/models` directory stores its trained model files. Docker Compose
mounts it into the backend container at `/app/models`.

```text
backend/models/
  device1/
    lstm_ae/
      v1/
        weights.bin
  device2/
    lstm_ae/
      v2/
        weights.bin
```

Device folders organize files only; there is no device field or relationship
on `ModelVersion`. Version numbers remain unique per algorithm across all
device folders. Choose a new version number when registering another set of
weights for the same algorithm.

## The mapping

| Location | Example |
| --- | --- |
| Project file | `backend/models/device1/lstm_ae/v1/weights.bin` |
| File inside Docker | `/app/models/device1/lstm_ae/v1/weights.bin` |
| Database `ModelArtifact.file` | `device1/lstm_ae/v1/weights.bin` |

Compose uses a **bind mount**: the container sees this host directory directly.
The mapping is configured in `compose.yaml`. The Dockerfile builds the program;
model weights stay outside the image. Restarting or rebuilding the container
preserves these files on the host. To move the application to another computer,
copy this directory's weights and restore the database together.

## Register a model, step by step

Training takes place outside the application. Obtain the trained weights and
create the model-version metadata first, including its algorithm, version,
architecture parameters and input specification. Currently metadata is created
through the Django shell; there is no model-management API or UI yet.

For example, after creating `lstm_ae` version 1 for a new setup, run these
PowerShell commands from the project root:

```powershell
# 1. Put the trained weights in their final local folder.
New-Item -ItemType Directory -Force ./backend/models/device1/lstm_ae/v1
if (Test-Path ./backend/models/device1/lstm_ae/v1/weights.bin) { throw "File already exists; choose a new version." }
Copy-Item -LiteralPath ./trained-model.pt -Destination ./backend/models/device1/lstm_ae/v1/weights.bin

# 2. Start/recreate the backend with the Compose mount.
docker compose up -d backend

# 3. Register the file with the UUID of the metadata record created above.
docker compose exec backend python manage.py register_model_weights "MODEL_VERSION_ID" /app/models/device1/lstm_ae/v1/weights.bin --device-folder device1
```

The registration command reads and checks the file without loading or executing
the neural network. Since the file is already at its destination, registration
reuses it and stores its relative path and size. Repeating the command with the
same weights checks the existing registration. There is no hashing.

Each version's weights should stay fixed. For new weights, create a new version
and directory. Keep a backup before replacing files manually: changes in this
directory are immediately visible inside the container.

Model binaries are ignored by Git; this README, `.gitignore` and the Compose
mapping are versioned. A fresh clone needs its trained weights copied here
before model files can be used. The registered legacy LSTM file is currently
`device1/lstm_ae/v1/weights.bin`.
It was copied from `legacy/checkpoints/device1/lstm_ae_epoch_1` and compared
byte-for-byte with the previously registered Docker file before switching mounts.

The previous Docker named volume `ts-anomaly-detection-web_model_artifacts` is
retained as a backup from before this mapping; the backend now uses this folder.

`/app/models` mirrors the project's `backend/models` folder. Django's internal setting
`MEDIA_ROOT` points to that directory; the folder does not have to be named
`media`. Without Docker, the default storage root is also the project's `backend/models`
directory. Migration 0008 removes the old `model_weights/` prefix from database
file references; it does not move or change the local weights.
