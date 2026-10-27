# PJME energy consumption pipeline

The shared dataset, Laura's databases, Gilbert's API and Tifare's forecasting code now use one record contract. The CSV contains 145,392 hourly records with `Datetime`, `PJME_MW`, `temperature_c` and `was_imputed`.

- `databases/`: Laura's three-table MySQL schema, MongoDB design, shared validation/configuration, batch loader and query tools.
- `api/`: Gilbert Muramirabagabo's CRUD and time-series endpoints, tests and integration evidence.
- `Tifare_forecasting/`: Tifare's saved model, shared training/inference preprocessing and forecast client.
- `pjme_clean.csv`: the single shared data file. Do not duplicate it in member folders.

## Verification status

Live integration is verified against MySQL 8.4.11 and MongoDB 8.0.34. The combined suite passed 150 tests with zero failures/errors. Both databases contain all 145,392 CSV records, and normalized record hashes match the source across every timestamp, demand, temperature and imputation flag. Both real API backends produced 32,562.82 MW for 2018-08-03 01:00:00. Offline tests remain available separately.

The historical database report remains labeled as a SQLite/pandas preview. The live exporter has now executed all four queries on each real server; actual results are in `databases/results/live_query_results.json`. Current test, dataset-integrity and forecast evidence is in `api/evidence/`.

## One environment for the group

From the repository root in PowerShell:

```powershell
python -m venv api/.venv
python -m pip --python api/.venv/Scripts/python.exe install -r requirements.txt
```

Python 3.13.2 was used for verification. `api/requirements-lock.txt` records the exact installed environment. The saved model was created with scikit-learn 1.9.1; its requirement is pinned to that version.

Check the dataset and run the integrated offline suite:

```powershell
& api/.venv/Scripts/python.exe -m databases.scripts.load_csv_to_databases --validate-only
& api/.venv/Scripts/python.exe -m pytest -c api/pytest.ini api/tests Tifare_forecasting/tests -q --junitxml=api/evidence/integration-offline-tests.xml
```

This validates both API contracts, database adapter behavior, CSV handling, forecasting edge cases, and the HTTP-to-saved-model path. It does not silently substitute test storage in the running application.

## Connect real databases when available

Copy `api/.env.example` to `api/.env` once, then set credentials for your own MySQL and MongoDB servers. Both database tools and the API use `databases/config.py`. Defaults are MySQL port 3307, MongoDB port 27018, and database `pjme_energy`. A normal native installation may use ports 3306 and 27017 instead.

Docker is optional. If available:

```powershell
docker compose -f api/compose.yaml up -d --wait
```

Compose now mounts Laura's actual SQL schema and the shared MongoDB initialization script. Existing Docker volumes are preserved; the explicit loader initializes the new database on an older volume too.

Load the current CSV into the real databases:

```powershell
& api/.venv/Scripts/python.exe -m databases.scripts.load_csv_to_databases
```

This validates the complete CSV first, then upserts records in batches. It preserves temperature and imputation flags. MySQL transactions include both calendar and reading rows. The databases commit independently, so rerun after a partial failure. Existing records at the same timestamp are updated to match the CSV.

For a smaller demonstration, use `--limit 200 --tail`; analytical results then cover only that sample. The loader requires schema-creation privileges; API credentials can be restricted to the initialized database afterwards. Incompatible old two-column tables are detected and require an explicit migration; no data is automatically dropped.

## Start the API and forecast

Start the server in one terminal:

```powershell
& api/.venv/Scripts/python.exe -m uvicorn api.app.main:app --host 127.0.0.1 --port 8000
```

Open [Swagger UI](http://127.0.0.1:8000/docs). In a second terminal, forecast using either database:

```powershell
& api/.venv/Scripts/python.exe -m Tifare_forecasting.scripts.predict --api-url "http://127.0.0.1:8000/mysql/records/recent?limit=200"
& api/.venv/Scripts/python.exe -m Tifare_forecasting.scripts.predict --api-url "http://127.0.0.1:8000/mongo/records/recent?limit=200"
```

`recent` selects the latest N observations and returns them oldest first under `records`. The model requires 168 consecutive, non-imputed hours ending at the latest timestamp. It recomputes features from observed demand using the same code as training.

## Real-database tests and evidence

```powershell
& api/.venv/Scripts/python.exe -m pytest -c api/pytest.ini api/tests Tifare_forecasting/tests --live-databases -q --junitxml=api/evidence/integration-live-tests.xml
& api/.venv/Scripts/python.exe -m databases.scripts.execute_queries_and_export_results
```

Live tests use randomly named temporary databases, not the group's imported records. The test MySQL account needs create/drop privileges. Set `TEST_MYSQL_HOST`, `TEST_MYSQL_PORT`, `TEST_MYSQL_USER`, `TEST_MYSQL_PASSWORD`, and `TEST_MONGO_URI` for servers other than the supplied local Compose setup.

The exporter runs four queries per real database and writes `databases/results/live_query_results.json`. It never labels offline calculations as live server output.

## Remaining team decisions

Confirm temperature provenance and the original timestamp timezone. Current storage and API responses preserve the cleaned CSV's naive clock labels; the model excludes temperature until its provenance and forecast-time availability are established. Database-stored historical lag snapshots are not used: derived features are calculated by the shared forecasting code.

See [API documentation](api/README.md), [integration contract](api/INTEGRATION.md), [database instructions](databases/README.md), and [forecasting documentation](Tifare_forecasting/README.md).
