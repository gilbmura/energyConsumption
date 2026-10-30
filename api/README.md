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

Temperature is required and cannot be null, matching Laura's SQL schema. Numeric values must be finite JSON numbers; demand cannot be negative. Flags must be booleans. Unknown fields are rejected. Timestamps must be naive ISO datetimes on hourly boundaries; date-only strings, offsets and nonzero fractional seconds are rejected. Range boundaries may use whole seconds.

Responses add `id` as a string: MySQL maps `reading_id`; MongoDB maps ObjectId `_id`. IDs cannot be shared across backends.

List and range responses contain `items`, `limit`, `offset` and `has_more`. Limits are 1–1000, default 200. Continue with offset increased by received item count. Recent responses contain `records` and intentionally select the end of the series; a regular list begins at the start.

## Validation and error handling

The examples below describe the implemented API contract for both `mysql` and `mongo`; they are illustrative responses, not a new live test run. Use [Swagger UI](http://127.0.0.1:8000/docs) to try requests with the API and the selected database running.

### Required fields and PUT replacement

POST and PUT require all four public fields shown above: `Datetime`, `PJME_MW`, `was_imputed` and `temperature_c`. Temperature cannot be null. Numbers must be finite JSON numbers, demand must be nonnegative, and `was_imputed` must be a JSON boolean (`true` or `false`). Extra fields, including an `id` in the request body, are rejected.

Record timestamps must use the dataset's local clock time without `Z` or a UTC offset and fall exactly on an hourly boundary. For example, `2018-01-01T00:00:00` is valid; `2018-01-01`, `2018-01-01T00:30:00` and `2018-01-01T00:00:00Z` are invalid. Nonzero fractional seconds and years before 1000 are rejected. Range boundaries allow whole seconds between hours, and `start` must be earlier than or equal to `end`.

PUT replaces all four public fields on an existing record. To change only demand, send the existing timestamp, imputation flag and temperature along with the new demand:

```http
PUT /{backend}/records/{id}
Content-Type: application/json
```

```json
{
  "Datetime": "2018-01-01T00:00:00",
  "PJME_MW": 34000.0,
  "was_imputed": false,
  "temperature_c": -4.4
}
```

Use the ID and existing values returned by the selected backend. A successful PUT returns 200 with the updated record; sending unchanged values also succeeds. A partial body such as `{"PJME_MW": 34000.0}` returns 422. PUT does not create a missing record. Backend metadata is handled as described under Database semantics below.

### IDs belong to their backend

Response IDs are strings. MySQL uses a positive integer `reading_id`, such as `"42"`; MongoDB uses a 24-character hexadecimal ObjectId, such as `"507f1f77bcf86cd799439011"`. These are format examples, not guaranteed existing records. Use the ID returned by that backend's POST or GET response for subsequent GET, PUT and DELETE requests. MySQL and MongoDB IDs are not interchangeable, even when the timestamp is the same.

### 422: invalid request

Omitting a required field, providing an invalid timestamp, using an invalid field type or supplying an extra field returns 422. For example, POST this body to `/{backend}/records`:

```json
{
  "Datetime": "2018-01-01T00:00:00",
  "PJME_MW": 32000.0,
  "was_imputed": false
}
```

Expected response because `temperature_c` is missing:

```json
{
  "detail": [
    {
      "loc": ["body", "temperature_c"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

An invalid timestamp produces a validation entry whose `loc` identifies `Datetime`. Invalid pagination values, such as `limit=0` or `limit=1001`, also return 422. A reversed date range returns `{"detail": "start must be earlier than or equal to end"}`.

Malformed IDs return 422 with a string `detail`, for example `{"detail": "MySQL IDs must be positive integers"}` for `/mysql/records/abc`, or `{"detail": "MongoDB IDs must be 24 hexadecimal characters"}` for `/mongo/records/abc`.

### 409: duplicate timestamp

Each backend enforces one observation per timestamp. POST with an existing timestamp, or PUT changing a record's timestamp to one belonging to another record in the same backend, returns 409:

```json
{"detail": "A record already exists at this Datetime"}
```

Retrieve the existing record and use its ID to update it if that is the intended operation. Timestamp uniqueness is enforced separately in MySQL and MongoDB.

### 404: record not found

GET, PUT or DELETE with a well-formed ID that does not exist in the selected backend returns 404. The latest-record endpoint also returns 404 when that backend contains no observations:

```json
{"detail": "Record not found"}
```

Empty list, date-range and recent-record queries instead return 200 with an empty `items` or `records` list in their usual response envelope.

### 503: database unavailable

When the running API encounters a MySQL or MongoDB driver error, such as a connection or authentication failure, the affected request returns 503:

```json
{"detail": "Database unavailable or not configured"}
```

The response hides connection details and credentials. Check the selected database's status, logs and `api/.env` settings using the [Docker operations guide](DOCKER_GUIDE.md). A successful `/health` response checks only API process liveness and does not prove database readiness. If the API itself is stopped, the client gets a connection failure rather than this HTTP response.

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
