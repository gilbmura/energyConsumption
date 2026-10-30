# Integration between database storage, API and forecasting

The pulled repository now supplies Laura's schema and Tifare's saved model. Gilbert's API has been adapted to both. The shared contract lives in `databases/records.py`; configuration lives in `databases/config.py` and is re-exported by the API.

## Integrated data flow

```text
Root pjme_clean.csv -> database loader -> MySQL / MongoDB
                   -> API recent history -> forecasting client -> next-hour demand
```

1. David's preprocessing notebook writes `data/processed/pjme_clean.csv`. Follow the [dataset handoff](../README.md#dataset-handoff) to synchronize the accepted output to the root `pjme_clean.csv`, which is the loader's default input and the training/mock input.
2. `databases.scripts.load_csv_to_databases` validates the complete CSV, provisions the canonical schema/indexes and upserts the four public fields into both databases by default. Each backend commits independently; the API does not mirror later edits between them.
3. Gilbert's API reads the selected database through `/mysql/records/recent?limit=200` or `/mongo/records/recent?limit=200`. Each returns the latest observations oldest first in a `records` envelope, including `Datetime`, `PJME_MW`, `was_imputed`, `temperature_c` and the backend's `id`.
4. `Tifare_forecasting.scripts.predict --api-url ...` fetches that history, requires 168 consecutive non-imputed hours ending at the latest timestamp, recomputes calendar/lag/rolling features, loads `Tifare_forecasting/models/pjme_forecast.joblib` and prints the next-hour forecast. The client does not write the forecast back to either database.

Training and `--mock` read the root CSV directly. Only `--api-url` exercises the database-to-API forecasting handoff. The full setup is in the [root README](../README.md); Docker runs the databases and Uvicorn starts the API separately.

## Storage contract

MySQL uses `pjme_energy.data_sources`, `time_dimensions` and `energy_readings`, provisioned from Laura's SQL file. API IDs map to `reading_id`. Creation resolves the seeded dataset/provider, or an explicit `MYSQL_SOURCE_ID`. Time-dimension and observation writes commit or roll back together. Updating a timestamp creates/reuses its new calendar row without moving the old parent key. Source and created-at metadata are retained; deletes retain dimension rows.

MongoDB uses `pjme_energy.energy_observations`. Core fields and derived calendar coordinates are maintained on each write. Both backends require unique timestamps and a numeric, non-null temperature. This replaces the original API's nullable-temperature assumption.

The cleaned CSV has 145,392 unique hourly timestamps and all four required fields. The batch loader now uses it by default and retains temperature and imputation flags. It no longer creates a conflicting two-column schema. The canonical bootstrap rejects an older incompatible reading table rather than silently dropping it.

## Forecast contract

`/mysql/records/recent?limit=200` and `/mongo/records/recent?limit=200` select the latest observations and return `{"records": [...]}` in chronological order. Existing list/range routes retain their `items` pagination contract.

The forecast client accepts records/items/data envelopes or a plain array, but rejects a paginated response with `has_more=true`. Prefer the dedicated recent endpoint. It requires at least 168 consecutive observed hours, uses the committed feature order and saved model, and rejects imputed data in that history.

Calendar and demand-derived model features are computed with Tifare's shared training/inference code. MongoDB's historical lag fields are not treated as current features; a CRUD update can invalidate features on later records too. The loader stops generating these caches, removes legacy feature fields on rows it reloads, and the API never returns them. No cross-document feature cache is claimed.

A final imputed observation now remains a missing value at the end of the time grid; it cannot silently shift the forecast backward to an earlier observation. Duplicate, non-hourly, infinite and negative demand input is rejected.

## Timestamp and temperature assumptions

Preserve the CSV's naive local clock labels. BSON stores them through its datetime representation without asserting that the original source was UTC. API responses have no timezone suffix. Confirm the original source timezone and daylight-saving policy before any conversion.

The [root README](../README.md#dataset-and-sources) documents Philadelphia temperature from the Open-Meteo Historical Archive: `temperature_2m`, requested latitude 39.95, longitude -75.16, dates 2002-01-01 through 2018-08-03, and timezone `America/New_York`. The raw file is `data/raw/philadelphia_temperature.csv`; preprocessing joins it to demand by `Datetime`. Philadelphia is an approximation for the wider PJM East region.

This documents the weather source and download configuration, but does not establish the original demand timezone or daylight-saving alignment of the joined clock labels. Prediction-time temperature availability also remains unverified. The loader and API retain and validate `temperature_c`; the saved forecasting model uses demand history and calendar features, not temperature.

## Completed live verification

The combined suite passed 150 tests with zero failures/errors against MySQL 8.4.11 and MongoDB 8.0.34. Live API tests created isolated temporary databases using Laura's canonical schema, exercised both backends and ran actual HTTP-to-model tests. The fixture removed only its generated test databases.

The shared CSV was then loaded into the project databases. Every one of the 145,392 observations matches the CSV in both stores: canonical SHA-256 digests agree across timestamp, demand, temperature and imputation flag. Both recent-history endpoints returned the expected latest 200 observations; the January 1–7 inclusive date range returned 168 records per backend.

Tifare's actual command-line client fetched history from each real API backend and produced 32,562.82 MW for 2018-08-03 01:00:00. The database query exporter executed all four analytical queries on each server. Result sizes were 10 daily peaks, 24 hourly groups, 168 date-range readings and 4 temperature groups for each database.

Evidence lives in `api/evidence/integration-live-tests.xml`, `http-live.json`, `pipeline-live-*.json`, `forecast-full-*.json`, `dataset-verification.json`, and `databases/results/live_query_results.json`. Offline evidence remains separately labeled and is not substituted for these live results.

## Reproducing the result

Follow the [root README](../README.md) to install the shared `api/.venv` environment, configure `api/.env`, start the databases, validate/load the root CSV and start Uvicorn on port 8000. Leave Uvicorn running and use a second PowerShell terminal at the repository root:

```powershell
& api/.venv/Scripts/python.exe -m Tifare_forecasting.scripts.predict --api-url "http://127.0.0.1:8000/mysql/records/recent?limit=200"
& api/.venv/Scripts/python.exe -m Tifare_forecasting.scripts.predict --api-url "http://127.0.0.1:8000/mongo/records/recent?limit=200"
```

Each command forecasts from one database. With the full documented CSV and committed model, the previously verified result was 32,562.82 MW for 2018-08-03 01:00:00. Changes to the latest records or model can change this result. The temporary verification API used port 8765; normal setup uses port 8000. Persistent Docker volumes retain the imported dataset. See [API tests and evidence](README.md#tests-and-evidence) to reproduce the live checks.

The remaining integration limitations are original demand timezone/daylight-saving alignment and prediction-time temperature availability. The code excludes temperature from model features and preserves dataset clock labels.
