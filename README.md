# Time-Series Anomaly Detection

A web platform for analyzing device test signals and detecting anomalies, with support for multiple models, sensors, and features planned.

## Goals

- Separate the frontend from an object-oriented Python/FastAPI backend.
- Build a React/TypeScript interface using an open-source admin template; Ant Design Pro is the proposed starting point.
- Support interchangeable detection models, starting with an LSTM autoencoder.
- Extend analysis to multiple sensors and derived features.
- Provide interactive signal charts, configurable analysis, and comparison of models and runs.
- Run the application and its services with Docker Compose.

## Current Status

The initial OOP backend, health endpoint, API documentation, and Docker setup are working. The next step is integrating the frontend and connecting it to the API.

Development proceeds in small, explained steps, keeping the code simple, readable, and maintainable.
