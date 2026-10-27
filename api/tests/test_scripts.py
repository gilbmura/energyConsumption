import csv
import io
from datetime import datetime, timedelta

import httpx
import pytest

from api.scripts import fetch_history as history
from api.scripts.seed_from_csv import load_records


def write_csv(tmp_path, values):
    path = tmp_path / "sample.csv"
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Datetime", "PJME_MW", "was_imputed", "temperature_c"])
    writer.writerows(values)
    path.write_text(buffer.getvalue(), encoding="utf-8")
    return path


def test_csv_boolean_is_parsed_without_truthy_string_bug(tmp_path):
    path = write_csv(
        tmp_path,
        [
            ["2018-01-01 00:00:00", "32000", "False", "-4.4"],
            ["2018-01-01 01:00:00", "33000", "True", "5"],
        ],
    )
    records = load_records(path, 2)
    assert records[0].was_imputed is False
    assert records[1].was_imputed is True
    assert records[1].temperature_c == 5
    assert len(load_records(path, 1)) == 1


def test_csv_reports_invalid_line(tmp_path):
    path = write_csv(tmp_path, [["2018-01-01 00:00:00", "32000", "unknown", "3"]])
    with pytest.raises(ValueError, match="line 2"):
        load_records(path, 10)


@pytest.mark.parametrize("hours", [168, 1001])
def test_history_follows_pagination_and_preserves_feature_names(monkeypatch, hours):
    records = [
        {
            "id": str(index + 1),
            "Datetime": (datetime(2018, 1, 1) + timedelta(hours=index)).isoformat(),
            "PJME_MW": 32000.0,
            "was_imputed": False,
            "temperature_c": -4.4,
        }
        for index in range(hours)
    ]
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("/latest"):
            return httpx.Response(200, json=records[-1])
        offset = int(request.url.params["offset"])
        limit = int(request.url.params["limit"])
        assert request.url.params["start"] == records[0]["Datetime"]
        assert request.url.params["end"] == records[-1]["Datetime"]
        return httpx.Response(
            200,
            json={"items": records[offset : offset + limit], "has_more": offset + limit < hours},
        )

    original_client = httpx.Client
    monkeypatch.setattr(
        history.httpx,
        "Client",
        lambda **kw: original_client(transport=httpx.MockTransport(handler), **kw),
    )
    assert history.fetch_history("http://test", "mysql", hours) == records
    assert len(calls) == 1 + (hours + 999) // 1000


def test_history_rejects_gaps(monkeypatch):
    record = {"Datetime": "2018-01-01T01:00:00"}

    def handler(request):
        return httpx.Response(
            200,
            json=record
            if request.url.path.endswith("/latest")
            else {"items": [record], "has_more": False},
        )

    original_client = httpx.Client
    monkeypatch.setattr(
        history.httpx,
        "Client",
        lambda **kw: original_client(transport=httpx.MockTransport(handler), **kw),
    )
    with pytest.raises(ValueError, match="incomplete history"):
        history.fetch_history("http://test", "mongo", 2)
