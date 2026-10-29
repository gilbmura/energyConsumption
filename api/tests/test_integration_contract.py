"""Regression tests for mismatches found during the team integration review."""

from datetime import datetime, timedelta
from pathlib import Path

import mongomock
import pandas as pd
import pytest

from api.app.repositories.mongo_repository import MongoRepository
from api.app.schemas import RecordWrite
from api.tests.test_api import BASE, insert
from databases.schema import initialize_mongo, schema_statements
from databases.scripts.load_csv_to_databases import read_records
from Tifare_forecasting.scripts.features import make_next_features, to_hourly_series

ROOT = Path(__file__).resolve().parents[2]


def test_recent_returns_latest_window_in_order(api_client):
    client, path = api_client
    rows = {hour: insert(client, path, hour) for hour in [4, 0, 3, 1, 2]}
    response = client.get(path + "/recent", params={"limit": 3})
    assert response.status_code == 200
    assert response.json() == {"records": [rows[2], rows[3], rows[4]]}


def test_recent_empty_and_invalid_limit(api_client):
    client, path = api_client
    assert client.get(path + "/recent").json() == {"records": []}
    assert client.get(path + "/recent?limit=0").status_code == 422
    assert client.get(path + "/recent?limit=1001").status_code == 422


def test_temperature_required_by_laura_schema(api_client):
    client, path = api_client
    assert client.post(path, json={**BASE, "temperature_c": None}).status_code == 422


def test_put_can_change_datetime_without_changing_record_id(api_client):
    client, path = api_client
    item = insert(client, path, 0)
    response = client.put(path + "/" + item["id"], json={**BASE, "Datetime": "2018-01-02T00:00:00"})
    assert response.status_code == 200
    assert response.json()["id"] == item["id"]
    assert response.json()["Datetime"] == "2018-01-02T00:00:00"


def test_mongo_calendar_and_source_survive_update():
    collection = mongomock.MongoClient().pjme_energy.energy_observations
    initialize_mongo(collection)
    repo = MongoRepository(collection)
    item = repo.create(RecordWrite(**BASE))
    document = collection.find_one()
    assert document["hour"] == 0 and document["day_of_week"] == 0
    assert document["source"] == "PJME_clean"
    collection.update_one(
        {}, {"$set": {"source": "teammate-source", "lag_1": 999, "metadata": "keep"}}
    )
    updated = repo.replace(item.id, RecordWrite(**{**BASE, "Datetime": "2018-01-06T15:00:00"}))
    assert updated.Datetime.hour == 15
    document = collection.find_one()
    assert (document["hour"], document["day_of_week"], document["is_weekend"]) == (15, 5, True)
    assert document["source"] == "teammate-source"
    assert document["metadata"] == "keep" and "lag_1" not in document


def test_mongo_indexes_accept_existing_equivalent_names():
    collection = mongomock.MongoClient().pjme_energy.energy_observations
    collection.create_index("Datetime", unique=True)  # Original loader's default index name.
    initialize_mongo(collection)
    initialize_mongo(collection)
    assert len(collection.index_information()) == 5


def test_schema_bootstrap_never_selects_the_production_database():
    statements = schema_statements()
    assert len([s for s in statements if s.startswith("CREATE TABLE")]) == 3
    assert all(not s.startswith(("USE ", "CREATE DATABASE")) for s in statements)
    assert any("temperature_c DOUBLE NOT NULL" in s for s in statements)


def test_loader_preserves_all_columns_and_can_select_latest_data():
    rows = read_records(ROOT / "pjme_clean.csv", limit=200, tail=True)
    assert len(rows) == 200
    assert rows[-1].Datetime == datetime(2018, 8, 3)
    assert rows[0].Datetime == rows[-1].Datetime - timedelta(hours=199)
    assert all(isinstance(row.was_imputed, bool) for row in rows)
    assert all(isinstance(row.temperature_c, float) for row in rows)


def test_imputed_last_hour_is_not_silently_truncated():
    records = [
        {**BASE, "Datetime": (datetime(2018, 1, 1) + timedelta(hours=i)).isoformat()}
        for i in range(200)
    ]
    records[-1]["was_imputed"] = True
    series = to_hourly_series(pd.DataFrame(records))
    assert series.index[-1] == pd.Timestamp(records[-1]["Datetime"])
    assert pd.isna(series.iloc[-1])
    with pytest.raises(ValueError, match="168 consecutive"):
        make_next_features(records)


@pytest.mark.parametrize(
    "change",
    [
        {"Datetime": "2018-01-01T00:30:00"},
        {"PJME_MW": float("inf")},
        {"PJME_MW": -1},
        {"was_imputed": "unknown"},
    ],
)
def test_forecasting_rejects_invalid_input(change):
    with pytest.raises(ValueError):
        to_hourly_series(pd.DataFrame([{**BASE, **change}]))
