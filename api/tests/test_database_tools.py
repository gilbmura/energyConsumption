"""Tests for safe loading, query selection and truthful evidence generation."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import mongomock
import pytest

from databases.queries import mongo_queries
from databases.schema import source_id
from databases.scripts import execute_queries_and_export_results as exporter
from databases.scripts.load_csv_to_databases import read_records

ROOT = Path(__file__).resolve().parents[2]


def test_loader_rejects_duplicate_timestamps_before_writes(tmp_path):
    path = tmp_path / "duplicate.csv"
    path.write_text(
        "Datetime,PJME_MW,temperature_c,was_imputed\n"
        "2018-01-01 00:00:00,30000,4,False\n"
        "2018-01-01 00:00:00,31000,5,True\n"
    )
    with pytest.raises(ValueError, match="Duplicate timestamp"):
        read_records(path, limit=1)


def test_source_lookup_uses_provisioned_metadata_not_hardcoded_id():
    cursor = MagicMock()
    cursor.fetchone.return_value = {"source_id": 17}
    assert source_id(cursor) == 17
    assert "dataset_name=%s AND provider=%s" in cursor.execute.call_args.args[0]
    assert source_id(cursor, configured_id=17) == 17
    assert cursor.execute.call_args.args[1] == (17,)


def test_live_export_failure_does_not_overwrite_previous_evidence(tmp_path, monkeypatch):
    output = tmp_path / "evidence.json"
    output.write_text('{"previous": true}')
    monkeypatch.setattr(sys, "argv", ["exporter", "--output", str(output)])

    def fail(_settings):
        raise ConnectionError("Database unavailable")

    monkeypatch.setattr(exporter, "collect_results", fail)
    with pytest.raises(ConnectionError):
        exporter.main()
    assert json.loads(output.read_text()) == {"previous": True}


def test_query_exporter_is_read_only_and_runs_four_queries():
    queries = exporter.sql_queries()
    assert set(queries) == set(mongo_queries())
    assert all(query.startswith("SELECT ") for query in queries.values())
    assert len(queries) == 4


def test_mongo_analytical_pipelines_handle_temperature_boundaries():
    collection = mongomock.MongoClient().pjme.energy_observations
    from datetime import datetime, timedelta

    collection.insert_many(
        [
            {
                "Datetime": datetime(2018, 1, 1) + timedelta(hours=i),
                "PJME_MW": 30000 + i,
                "temperature_c": temperature,
                "hour": i,
                "was_imputed": False,
            }
            for i, temperature in enumerate([-1, 0, 15, 16, 25, 26])
        ]
    )
    results = {
        name: list(collection.aggregate(pipeline)) for name, pipeline in mongo_queries().items()
    }
    assert len(results["daily_peaks"]) == 1
    assert len(results["date_range"]) == 6
    assert len(results["hourly_profile"]) == 6
    assert [row["observations"] for row in results["temperature_profile"]] == [1, 2, 2, 1]
