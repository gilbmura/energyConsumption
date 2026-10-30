# Gilbert Muramirabagabo — Task 3 API

This folder owns the HTTP API, database adapters, tests and forecasting handoff. It now uses Laura's actual schema in `databases/mysql/schema.sql` and her `energy_observations` MongoDB collection. Run commands from the repository root.

## Setup

Follow the [root README](../README.md) for the combined environment, database loading and forecasting commands. Both the database tools and API read `api/.env` through `databases/config.py`.

See the [local Docker operations guide](DOCKER_GUIDE.md) for database startup, ports, logs, shutdown, volume persistence and troubleshooting.

```powershell
& api/.venv/Scripts/python.exe -m uvicorn api.app.main:app --host 127.0.0.1 --port 8000
```

[Swagger UI](http://127.0.0.1:8000/docs) documents every endpoint. The service binds to localhost and has no authentication; internet deployment is outside this assignment implementation. `/health` checks process liveness, not database readiness. Missing/unavailable database configuration returns a sanitized 503 on data routes.

## Module boundaries

- `app/main.py`: application lifecycle, error responses and route registration.
- `app/routes/records.py`: identical endpoint behavior for both backends.
- `app/schemas.py`: HTTP envelopes over the shared observation model in `databases/records.py`.
- `app/dependencies.py`: connections and adapter injection.
- `app/repositories/mysql_repository.py`: SQL operations and transactions.
- `app/repositories/mongo_repository.py`: MongoDB operations and calendar fields.
- `scripts/`: CSV sample import through HTTP and history retrieval.
- `tests/`: API, adapter, regression and HTTP-to-model tests.
- `evidence/`: generated verification files and their interpretation.

The temporary `api/dev/mysql.sql` and `api/dev/mongo.js` were removed after their references were changed to the shared database files. Keep `compose.yaml`; it now provisions the real schema for local testing.

## Routes

Substitute `mysql` or `mongo` for `{backend}`.

- `POST /{backend}/records`: create; returns 201 and a Location header.
- `GET /{backend}/records`: ascending paginated records.
- `GET /{backend}/records/{id}`: one record.
- `PUT /{backend}/records/{id}`: full replacement of the four public fields; does not upsert.
- `DELETE /{backend}/records/{id}`: delete one observation; returns 204 without a body.
- `GET /{backend}/records/latest`: observation with the greatest timestamp.
- `GET /{backend}/records/recent?limit=200`: latest N observations, returned oldest first under `records`; use for Tifare's forecast script.
- `GET /{backend}/records/range?start=2018-01-01T00:00:00&end=2018-01-07T23:00:00`: inclusive boundaries, ascending order.

POST and PUT require:

```json
{
  "Datetime": "2018-01-01T00:00:00",
  "PJME_MW": 32000.0,
  "was_imputed": false,
  "temperature_c": -4.4
}
```

Temperature is required and cannot be null, matching Laura's SQL schema. Numeric values must be finite JSON numbers; demand cannot be negative. Flags must be booleans. Unknown fields are rejected. Timestamps must be naive ISO datetimes on hourly boundaries; date-only strings, offsets and fractional seconds are rejected. Range boundaries may use whole seconds.

Responses add `id` as a string: MySQL maps `reading_id`; MongoDB maps ObjectId `_id`. IDs cannot be shared across backends.

List and range responses contain `items`, `limit`, `offset` and `has_more`. Limits are 1–1000, default 200. Continue with offset increased by received item count. Recent responses contain `records` and intentionally select the end of the series; a regular list begins at the start.

Validation failures return 422, duplicates return 409, missing records return 404, and database failures return 503. Empty list/range/recent queries return 200 with empty lists. Unchanged PUT succeeds.

## Database semantics

MySQL POST resolves the seeded data source and creates/reuses the timestamp's calendar row in the same transaction as the reading. PUT preserves source/creation metadata and handles timestamp changes transactionally. DELETE removes only the observation; calendar and provenance rows remain.

MongoDB POST stores all four fields, calendar fields, and `source: PJME_clean`. PUT updates the calendar and public fields while preserving unrelated metadata. Old lag/rolling snapshots on the updated document are removed. Such snapshots elsewhere are ignored; the forecast client recomputes all features from raw history. No multi-document feature cache is maintained.

Both backends require the provisioned unique timestamp index. The application does not silently create schemas at startup, mirror writes to the other backend, or claim a distributed transaction. Offset pagination assumes a stable history while pages are fetched.

## Tests and evidence

Install the root requirements, then:

```powershell
& api/.venv/Scripts/python.exe -m pytest -c api/pytest.ini api/tests Tifare_forecasting/tests -q --junitxml=api/evidence/integration-offline-tests.xml
& api/.venv/Scripts/python.exe -m ruff check --config api/pyproject.toml api
```

Use `--live-databases` after real servers are ready. The live fixture provisions Laura's canonical schema in random temporary databases and only deletes those test databases. The production dataset is not cleared.

[Evidence notes](evidence/README.md) explain simulated storage versus real HTTP and actual database persistence. [INTEGRATION.md](INTEGRATION.md) records the team interfaces and remaining verification.

## Useful helpers

```powershell
& api/.venv/Scripts/python.exe -m api.scripts.seed_from_csv --backend mysql --limit 200 --tail
& api/.venv/Scripts/python.exe -m api.scripts.seed_from_csv --backend mongo --limit 200 --tail
& api/.venv/Scripts/python.exe -m api.scripts.fetch_history --backend mysql --hours 168
```

The HTTP importer skips existing timestamps without comparing or overwriting them. The database batch loader instead upserts all fields from the CSV; choose deliberately. Both validate the full source first. History retrieval checks hourly continuity; Tifare's feature code additionally rejects imputed observations.

References: [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/), [PyMySQL transactions](https://pymysql.readthedocs.io/en/latest/user/examples.html), [MySQL foreign keys](https://dev.mysql.com/doc/refman/8.0/en/create-table-foreign-keys.html).
