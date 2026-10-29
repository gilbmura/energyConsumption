# Integration between database storage, API and forecasting

The pulled repository now supplies Laura's schema and Tifare's saved model. Gilbert's API has been adapted to both. The shared contract lives in `databases/records.py`; configuration lives in `databases/config.py` and is re-exported by the API.

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

Temperature's provenance and prediction-time availability are still unverified. The API stores and validates it, but the model does not use it as a predictor.

## Completed live verification

The combined suite passed 150 tests with zero failures/errors against MySQL 8.4.11 and MongoDB 8.0.34. Live API tests created isolated temporary databases using Laura's canonical schema, exercised both backends and ran actual HTTP-to-model tests. The fixture removed only its generated test databases.

The shared CSV was then loaded into the project databases. Every one of the 145,392 observations matches the CSV in both stores: canonical SHA-256 digests agree across timestamp, demand, temperature and imputation flag. Both recent-history endpoints returned the expected latest 200 observations; the January 1–7 inclusive date range returned 168 records per backend.

Tifare's actual command-line client fetched history from each real API backend and produced 32,562.82 MW for 2018-08-03 01:00:00. The database query exporter executed all four analytical queries on each server. Result sizes were 10 daily peaks, 24 hourly groups, 168 date-range readings and 4 temperature groups for each database.

Evidence lives in `api/evidence/integration-live-tests.xml`, `http-live.json`, `pipeline-live-*.json`, `forecast-full-*.json`, `dataset-verification.json`, and `databases/results/live_query_results.json`. Offline evidence remains separately labeled and is not substituted for these live results.

## Reproducing the result

Follow the root README to start the databases, load the CSV, run the live suite and start the API. The temporary verification API used localhost port 8765; normal setup uses port 8000. The persistent Docker volumes retain the imported dataset.

Temperature provenance and original timestamp timezone remain team documentation questions. The code deliberately excludes temperature from model features and preserves dataset clock labels. No commits or pushes were made automatically.
