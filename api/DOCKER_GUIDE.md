# Local Docker operations guide

Docker Compose runs this project's **MySQL and MongoDB databases**. FastAPI and the forecasting client run separately through `api/.venv`.

Run these Windows PowerShell commands from the repository root, containing `api/`, `databases/` and `pjme_clean.csv`. Complete the [environment setup](../README.md#environment-setup) before running Python commands.

## Services and ports

[compose.yaml](compose.yaml) defines the project `gilbert-energy-api`:

- `mysql` uses `mysql:8.4`: host address `127.0.0.1:3307` forwards to container port `3306`.
- `mongo` uses `mongo:8.0`: host address `127.0.0.1:27018` forwards to container port `27017`.
- Both use database `pjme_energy`; MongoDB observations use collection `energy_observations`.
- Ports bind to localhost. Data persists in named volumes `mysql_data` and `mongo_data`, normally prefixed with the Compose project name.

The API and loader read `databases/config.py`, with overrides from `api/.env` and environment variables.

## Start the databases

Open Docker Desktop and wait for its Linux container engine. Run these commands in order, resolving any error before proceeding:

```powershell
docker info
docker compose -f api/compose.yaml up -d --wait
docker compose -f api/compose.yaml ps
```

First startup may download images and initialize volumes. `-d` runs containers in the background; `--wait` waits for readiness. Both services have health checks, so confirm both report healthy.

Healthy means the database process responds. It does not prove that the CSV is loaded, application credentials work, or FastAPI is running.

## Configure and load data

Create configuration only if it does not already exist:

```powershell
if (-not (Test-Path api/.env)) {
    Copy-Item -LiteralPath api/.env.example -Destination api/.env
}
```

Review settings against Compose. Host Python uses MySQL port `3307` and MongoDB port `27018`. Keep private credentials out of Git.

Fresh volumes run the SQL schema and MongoDB initialization script mounted from `databases/`. Compose does not import the CSV. Validate first, resolve any errors, then load:

```powershell
& api/.venv/Scripts/python.exe -m databases.scripts.load_csv_to_databases --validate-only
& api/.venv/Scripts/python.exe -m databases.scripts.load_csv_to_databases
```

The loader provisions the canonical schema/indexes and upserts the root `pjme_clean.csv`. Rerunning it can replace database values at matching timestamps with CSV values. Each database commits independently. A normal restart does not require reloading correct existing data.

Initialization scripts are not reapplied to existing volumes on every restart. Changing `api/.env` changes application settings, not database accounts or passwords already stored in a volume.

## Start the API separately

With databases healthy and populated, run:

```powershell
& api/.venv/Scripts/python.exe -m uvicorn api.app.main:app --host 127.0.0.1 --port 8000
```

Keep this terminal running and open [Swagger UI](http://127.0.0.1:8000/docs). In another terminal at the repository root, check both database-backed routes:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/mysql/records/latest'
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/mongo/records/latest'
```

These requests only read data. `/health` checks process liveness, not database readiness. See the [API README](README.md) for endpoint behavior and [forecasting instructions](../README.md#task-4-forecasting-api-integration) for client commands.

## Inspect status and logs

Include stopped containers when diagnosing problems:

```powershell
docker compose -f api/compose.yaml ps --all
```

Read recent messages from both services:

```powershell
docker compose -f api/compose.yaml logs --tail=100 mysql mongo
```

Follow new messages during troubleshooting:

```powershell
docker compose -f api/compose.yaml logs --follow --tail=50 mysql mongo
```

Press `Ctrl+C` to stop following logs; containers remain running. Replace `mysql mongo` with one service name to inspect it alone. Review logs for private information before sharing them.

To restart database processes and wait for readiness:

```powershell
docker compose -f api/compose.yaml restart mysql mongo
docker compose -f api/compose.yaml up -d --wait
```

Restarting interrupts database access temporarily. `restart` does not apply changed Compose configuration; use `up -d --wait` after intentional configuration changes.

## Stop work while preserving data

Stop Uvicorn with `Ctrl+C` in its terminal. Choose one database shutdown option:

Stop containers while retaining them for reuse:

```powershell
docker compose -f api/compose.yaml stop
```

Or stop and remove project containers and the network, preserving named database volumes:

```powershell
docker compose -f api/compose.yaml down
```

Resume either way with `docker compose -f api/compose.yaml up -d --wait`, then start Uvicorn again. Stopping databases does not stop the separate Python API, and stopping Uvicorn does not stop databases.

## Deliberately reset database contents

**Data deletion:** adding `-v` to `down` removes this project's named volumes and their MySQL/MongoDB contents. Use this only to intentionally discard local database data after preserving anything needed. It is not routine shutdown or a first response to a connection error.

```powershell
docker compose -f api/compose.yaml down -v
```

After an intentional reset, start services with `up -d --wait` and run the CSV loader again. This restores CSV observations but cannot recover API edits or other records stored only in the deleted volumes. Repository files and the source CSV are not deleted by this command.

## Troubleshooting

### Docker command is not recognized

Confirm Docker Desktop and its CLI are installed, then open a new PowerShell terminal. The `docker compose` command must also be available.

### Cannot connect to the engine or named pipe

Wait for Docker Desktop's Linux engine and retry `docker info` in your normal user terminal. For access-denied errors, check Docker Desktop access for your Windows account. Deleting database volumes does not fix engine access.

### A host port is already in use

Check whether another database or container uses `3307` or `27018` and resolve the conflict. If the team changes the Compose mappings, update the corresponding application settings too.

### Startup times out or a service is unhealthy

Use `ps --all` and service logs to identify the failing database. Resolve the logged error, then retry `up -d --wait`. Distinguish a slow first download or initialization from repeated failures.

### API requests return 503

Check container health, then the API's host, port, database and credentials. `api/.env` must match the existing database accounts; editing it does not reset their passwords. Restart Uvicorn after changing application settings. Inspect its terminal as well as database logs.

### Latest-record requests return 404

An empty database can pass its Docker health check. Confirm which database the API uses and run the CSV loader if it has not been populated.

### The loader reports an incompatible schema

The loader rejects incompatible older tables. Review the error and plan a migration or an intentional disposable-data reset. Do not automatically remove volumes: they may contain work absent from the CSV.
