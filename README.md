# Time-Series Anomaly Detection

A web platform for analyzing device test signals and detecting anomalies, with support for multiple models, sensors, and features planned.

## Goals

- Separate the frontend from an object-oriented Python backend built with Django and Django REST Framework (DRF).
- Build a React/TypeScript interface using an open-source admin template; Ant Design Pro is the proposed starting point.
- Support interchangeable detection models, starting with an LSTM autoencoder.
- Extend analysis to multiple sensors and derived features.
- Provide interactive signal charts, configurable analysis, and comparison of models and runs.
- Run the application and its services with Docker Compose.

## Current Status

The Django and DRF backend, React frontend, PostgreSQL setup, health endpoint, and API are working together. Current-format DAT files can be previewed and imported. Each import request creates one measurement batch with device serials, tests, and signal traces. The batch has one receipt timestamp; each test retains its own execution timestamp. Imported test runs store their complete signal samples and flat results; the serial-batches page shows batches, serials, tests, and parameter tables. The same DAT may be imported again as a separate batch.

The serial-details toolbar plots the selected test's signals in a zoomable dialog. PDF and full Excel actions default to the selected test; their dropdown menus also export every test in the current serial. Full Excel includes metadata, each test's own parameter columns, and all raw signal samples in separate worksheets. Table Excel exports only the visible parameter table. Reports are generated in the frontend from cached measurement data; signal samples load on demand. PDF opens a print-ready report with parameter tables and signal charts; choose **Save as PDF** in the browser's print dialog.

Development proceeds in small, explained steps, keeping the code simple, readable, and maintainable.

See [backend development](backend/README.md) for test organization and commands.

## Model files

Trained weights are organized in `backend/models/<device-folder>/<algorithm>/v<version>/weights.bin`.
Docker Compose mounts `./backend/models` at `/app/models` in the backend,
so local files are visible inside Docker. The database keeps relative file paths
and model metadata; device names are used for folder organization only.

See [the model storage walkthrough](backend/models/README.md) for the folder layout,
the local-to-container mapping and registration steps. Model binaries are ignored
by Git and should be backed up together with the database.
