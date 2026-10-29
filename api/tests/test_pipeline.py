"""Actual HTTP -> shared feature engineering -> committed model.

By default SQL storage is a repository double and Mongo storage uses mongomock.
--live-databases switches to the real adapters and real database servers.
"""

import json
import socket
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import joblib
import mongomock
import pytest
import uvicorn

from api.app.dependencies import get_mongo_repository
from api.app.repositories.mongo_repository import MongoRepository
from databases.schema import initialize_mongo
from databases.scripts.load_csv_to_databases import read_records
from Tifare_forecasting.scripts.predict import forecast, get_records

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def http_api(api_client, backend, live_settings):
    client, path = api_client
    if backend == "mongo" and not live_settings:
        collection = mongomock.MongoClient().pjme_energy.energy_observations
        initialize_mongo(collection)
        client.app.dependency_overrides[get_mongo_repository] = lambda: MongoRepository(collection)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    config = uvicorn.Config(client.app, log_level="error", lifespan="off")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("Local API test server did not start")
            time.sleep(0.01)
        yield f"http://127.0.0.1:{port}", path
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()


def test_http_to_saved_model_pipeline(http_api, backend, live_settings):
    base_url, path = http_api
    rows = read_records(ROOT / "pjme_clean.csv", limit=200, tail=True)
    with httpx.Client(base_url=base_url, timeout=15) as client:
        for row in rows:
            response = client.post(path, json=row.model_dump(mode="json"))
            assert response.status_code == 201, response.text
    endpoint = base_url + path + "/recent?limit=200"
    records = get_records(url=endpoint)
    assert len(records) == 200
    assert records[-1]["was_imputed"] is False
    artifact = joblib.load(ROOT / "Tifare_forecasting" / "models" / "pjme_forecast.joblib")
    timestamp, prediction = forecast(records, artifact)
    expected_time, expected_prediction = forecast(
        [row.model_dump(mode="json") for row in rows], artifact
    )
    assert timestamp == expected_time
    assert prediction == expected_prediction
    assert str(timestamp) == "2018-08-03 01:00:00"
    assert prediction > 0
    mode = "live" if live_settings else "offline"
    evidence = {
        "mode": "real databases" if live_settings else "test storage; not real database evidence",
        "backend": backend,
        "transport": "actual localhost HTTP through FastAPI/Uvicorn",
        "storage": backend
        if live_settings
        else ("mongomock" if backend == "mongo" else "MemoryRepository"),
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "history_records": len(records),
        "latest_observation": records[-1]["Datetime"],
        "forecast_for": str(timestamp),
        "predicted_PJME_MW": prediction,
        "matches_direct_csv_prediction": True,
    }
    (ROOT / "api" / "evidence" / f"pipeline-{mode}-{backend}.json").write_text(
        json.dumps(evidence, indent=2), encoding="utf-8"
    )
