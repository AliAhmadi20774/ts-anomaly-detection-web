# Backend development

## Tests

Each app keeps its tests in a `tests/` Python package, next to the code it covers.
Files use `test_<subject>.py` names. Keep `tests/__init__.py` empty so importing
the package does not load unrelated tests or require database configuration.

```text
backend/
  accounts/tests/
  algorithms/tests/
    test_algorithms.py
    test_artifacts.py
    test_model_versions.py
    test_models_root_migration.py
    test_normalization.py
    test_preprocessing_metadata.py
    test_storage_only_migration.py
    test_windowing.py
  dat_imports/tests/
  devices/tests/
  health/tests/
  sample_data/tests/
```

The algorithm primitive tests use standard-library `unittest` and need no
Django settings or database. From `backend/`, with the project's Python
environment active:

```powershell
python -m unittest algorithms.tests.test_normalization algorithms.tests.test_windowing -v
```

For the complete suite, configure `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER` and
`PGPASSWORD` for a disposable PostgreSQL instance, then run from `backend/`:

```powershell
python manage.py test --noinput
```

The test role must be allowed to create the temporary test database. Do not
grant extra privileges to the application's normal database role. Django
discovers the app test packages and `sample_data/tests/` automatically when run
from this directory. A specific app can be selected with a label such as
`python manage.py test algorithms.tests --noinput`.

Tests requiring models or APIs use Django/DRF test cases. Migration tests use
transactional test cases and restore the latest schema during cleanup. Shared
test helpers should live inside the relevant `tests/` package rather than in
production modules or package initialization files.
