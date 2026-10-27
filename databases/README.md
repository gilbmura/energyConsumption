# Laura Karangwa — Task 2 databases

The canonical design uses MySQL database `pjme_energy` with three related tables, and MongoDB database `pjme_energy` with collection `energy_observations`. The shared cleaned CSV has 145,392 hourly records, including 30 imputation flags.

The API now uses this schema directly. See the [root setup guide](../README.md) and [shared integration contract](../api/INTEGRATION.md).

## Source files

- `mysql/schema.sql`: the authoritative three-table DDL and initial data-source metadata.
- `mysql/queries.sql`: four analytical SQL queries.
- `mongodb/init.js`: MongoDB indexes for fresh local containers.
- `mongodb/collection_design.md`: active document format and datetime semantics.
- `mongodb/queries.js`: the analytical queries for mongosh.
- `mongodb/sample_documents.json`: JSON examples from the cleaned CSV, not directly inserted BSON documents.
- `docs/erd.md` and `docs/erd_diagram.png`: relational design.
- `config.py`, `records.py`, `schema.py`: shared connections, validation and provisioning helpers.
- `scripts/load_csv_to_databases.py`: the real database batch loader.
- `scripts/execute_queries_and_export_results.py`: the real server query exporter.
- `scripts/preview_queries_from_csv.py`: optional SQLite/pandas preview, clearly separate from real evidence.

## Database design

`data_sources` stores provenance. `time_dimensions` stores one row per timestamp with hour, weekday, month and weekend fields. `energy_readings` stores demand, temperature, imputation status, and foreign keys to both dimensions.

`temperature_c` is required by the SQL schema. The loader/API enforce that contract. Timestamp uniqueness is enforced in both stores. The API returns the same public JSON fields for either backend.

MongoDB stores observations and calendar fields together. Historical lag snapshots are not maintained by mutable CRUD operations and are not used by forecasting. The model recomputes them from returned observations.

## Run from the repository root

Install the root requirements and configure `api/.env`. Docker is optional; native database servers can be used by setting their actual host, port and credentials.

```powershell
& api/.venv/Scripts/python.exe -m databases.scripts.load_csv_to_databases --validate-only
& api/.venv/Scripts/python.exe -m databases.scripts.load_csv_to_databases
& api/.venv/Scripts/python.exe -m databases.scripts.execute_queries_and_export_results
```

The loader validates the complete file before writing. It initializes Laura's schema, preserves all four fields, and performs upserts in batches. A failure can leave earlier batches committed; rerunning repairs the selected rows. Backends commit independently. Use `--backend mysql`, `--backend mongo`, or `--limit 200 --tail` when needed.

Database names and connection parameters come from `config.py`; the old `MYSQL_URL` loader setting is no longer used. On an existing incompatible two-column schema, the loader stops and asks for an explicit migration rather than dropping data.

## Evidence provenance

`results/query_execution_results.md` is a historical preview generated with SQLite and pandas. It is now labeled accordingly; it is not proof that MySQL and MongoDB were run.

The new exporter executes all four SQL queries and their PyMongo equivalents on actual servers. It records server versions, queries, responses and counts in `results/live_query_results.json`, and writes the file only after both servers succeed. This has now run successfully on MySQL 8.4.11 and MongoDB 8.0.34, each containing 145,392 records. Full normalized record hashes also match the source CSV.

For offline exploration only:

```powershell
& api/.venv/Scripts/python.exe -m databases.scripts.preview_queries_from_csv
```

This writes a separate `results/csv_preview_results.md`. The optional interactive `explore_databases.py` tool uses SQLite, not either live database, and additionally requires `rich`.

The source and time alignment of temperature still need team documentation; numeric validation does not establish provenance.
