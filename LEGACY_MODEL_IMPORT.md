# Import real server model settings

Use the real server config and weights, rather than the sample files in this project. Back up the destination database and `backend/models` first.

## 1. Prepare the old files

Keep this layout:

```text
old-app/src/config/global_config.py
old-app/checkpoints/<device>/<weights-file>
```

The config must contain a plain dictionary declared as `CONFIG: dict = {...}`. Weight paths must be relative to `old-app`, for example `checkpoints/device1/model.pt`.

The current exporter supports **LSTM-AE, one signal named `signal1`, raw data at 1000 Hz, `["mean"]`, and no normalization**. If the real model uses other settings, update the exporter before importing. It does not run Python code inside the config.

## 2. Export a bundle

Run from the new project's root. Replace the old application path. On Linux, use `python3` if needed.

```bash
python scripts/export_legacy_models.py "/path/to/old-app" backend/models/imports/server-01
```

Use a new output folder each time. The bundle contains `manifest.json` and copies of the weights. To use another server, copy the whole bundle there.

## 3. Start the backend

The destination PostgreSQL connection and `.env` must already be configured.

```bash
docker compose up -d --build backend
docker compose exec -T backend python manage.py migrate --noinput
```

## 4. Preview first

```bash
docker compose exec -T backend python manage.py import_model_bundle /app/models/imports/server-01/manifest.json
```

This checks the settings and weights without changing stored files or database records. Check the model list and settings in `manifest.json` too.

Versions start at 1. If a version conflicts with an existing model, choose a free number. Update its `version`, weight path, weight folder and matching `legacy.bindings` entries in the bundle, then preview again. Do not delete existing models to bypass a conflict.

## 5. Import

```bash
docker compose exec -T backend python manage.py import_model_bundle /app/models/imports/server-01/manifest.json --apply
```

Success shows `Imported N model(s)`. Repeating the same import does not create duplicates.

## What is saved

- **Database:** model version, architecture, input settings, preprocessing, weight path and file size.
- **Disk:** weights under `backend/models/<device>/lstm_ae/v<version>/weights.bin`. Docker sees the same folder at `/app/models`.
- **JSON only:** test assignments, section ranges, stride, batch size, thresholds and signal length rules. These are not yet active database settings.

Importing does not start anomaly detection. Keep the bundle with your database and model backups; model files are not included in Git or the Docker image.

See [the backend model documentation](backend/algorithms/README.md) for details.
