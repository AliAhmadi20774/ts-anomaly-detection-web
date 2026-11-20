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

The Django and DRF backend, React frontend, PostgreSQL setup, health endpoint, and API are working together. Current-format DAT files can be previewed and imported. Each import request creates one measurement batch with device serials, tests, and signal traces. The batch has one receipt timestamp; each test retains its own execution timestamp. Imported test runs store their complete signal samples and flat results; the serial-batches page shows batches, serials, tests, and signal charts. The same DAT may be imported again as a separate batch.

Development proceeds in small, explained steps, keeping the code simple, readable, and maintainable.
