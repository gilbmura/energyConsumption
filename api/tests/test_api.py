"""HTTP contract tests; use --live-databases to repeat against real storage."""

import json
from datetime import datetime, timedelta

import pytest

BASE = {
    "Datetime": "2018-01-01T00:00:00",
    "PJME_MW": 32000.0,
    "was_imputed": False,
    "temperature_c": -4.4,
}


def insert(client, path, hour=0, **changes):
    body = {
        **BASE,
        "Datetime": (datetime(2018, 1, 1) + timedelta(hours=hour)).isoformat(),
        **changes,
    }
    response = client.post(path, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_crud_lifecycle(api_client):
    client, path = api_client
    response = client.post(path, json=BASE)
    assert response.status_code == 201
    item = response.json()
    assert isinstance(item["id"], str)
    location = response.headers["Location"]
    assert location == path + "/" + item["id"]
    assert client.get(location).json() == item
    replacement = {**BASE, "PJME_MW": 34000, "temperature_c": 2.5, "was_imputed": True}
    response = client.put(location, json=replacement)
    assert response.status_code == 200
    assert response.json() == {**replacement, "id": item["id"]}
    assert client.get(location).json() == response.json()
    assert client.put(location, json=replacement).status_code == 200  # unchanged PUT
    assert client.delete(location).status_code == 204
    assert client.get(location).status_code == 404
    assert client.delete(location).status_code == 404


def test_empty_queries(api_client):
    client, path = api_client
    assert client.get(path + "/latest").status_code == 404
    page = client.get(path).json()
    assert page == {"items": [], "limit": 200, "offset": 0, "has_more": False}
    response = client.get(
        path + "/range", params={"start": BASE["Datetime"], "end": BASE["Datetime"]}
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_latest_uses_timestamp_not_insertion_order(api_client):
    client, path = api_client
    newest = insert(client, path, 10)
    insert(client, path, 0)
    assert client.get(path + "/latest").json() == newest


def test_range_includes_both_boundaries_and_orders_ascending(api_client):
    client, path = api_client
    records = {hour: insert(client, path, hour) for hour in [3, 0, 2, 1]}
    response = client.get(
        path + "/range", params={"start": records[1]["Datetime"], "end": records[2]["Datetime"]}
    )
    assert response.status_code == 200
    assert response.json()["items"] == [records[1], records[2]]
    response = client.get(
        path + "/range", params={"start": records[1]["Datetime"], "end": records[1]["Datetime"]}
    )
    assert response.json()["items"] == [records[1]]


@pytest.mark.parametrize("ranged", [False, True])
def test_pagination_has_no_missing_or_duplicate_records(api_client, ranged):
    client, path = api_client
    records = [insert(client, path, hour) for hour in [2, 0, 1]]
    params = {"limit": 2}
    if ranged:
        path += "/range"
        params.update(start="2018-01-01T00:00:00", end="2018-01-01T02:00:00")
    page1 = client.get(path, params=params).json()
    page2 = client.get(path, params={**params, "offset": 2}).json()
    assert page1["has_more"] is True
    assert page2["has_more"] is False
    assert page1["items"] + page2["items"] == sorted(records, key=lambda item: item["Datetime"])


def test_duplicate_create_and_update_do_not_corrupt_existing_data(api_client):
    client, path = api_client
    first = insert(client, path, 0)
    second = insert(client, path, 1)
    assert client.post(path, json=BASE).status_code == 409
    response = client.put(path + "/" + second["id"], json=BASE)
    assert response.status_code == 409
    assert client.get(path + "/" + first["id"]).json() == first
    assert client.get(path + "/" + second["id"]).json() == second


@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_valid_but_missing_id(api_client, backend, method):
    client, path = api_client
    record_id = "9223372036854775807" if backend == "mysql" else "ffffffffffffffffffffffff"
    kwargs = {"json": BASE} if method == "put" else {}
    assert getattr(client, method)(path + "/" + record_id, **kwargs).status_code == 404


@pytest.mark.parametrize("record_id", ["not-an-id", "-1", "0", "1 OR 1=1", "9" * 40])
def test_invalid_ids(api_client, record_id):
    client, path = api_client
    assert client.get(path + "/" + record_id).status_code == 422


@pytest.mark.parametrize(
    "changes",
    [
        {"PJME_MW": -1},
        {"PJME_MW": "32000"},
        {"PJME_MW": True},
        {"PJME_MW": None},
        {"temperature_c": "cold"},
        {"temperature_c": None},
        {"temperature_c": False},
        {"was_imputed": "False"},
        {"was_imputed": 1},
        {"Datetime": "bad"},
        {"Datetime": "2018-01-01"},
        {"Datetime": 1514764800},
        {"Datetime": "2018-01-01T00:00:00Z"},
        {"Datetime": "2018-01-01T00:00:00+02:00"},
        {"Datetime": "2018-01-01T00:30:00"},
        {"Datetime": "2018-01-01T00:00:00.000001"},
        {"Datetime": "0999-01-01T00:00:00"},
        {"unexpected": 1},
    ],
)
def test_validation_rejects_bad_records(api_client, changes):
    client, path = api_client
    assert client.post(path, json={**BASE, **changes}).status_code == 422


@pytest.mark.parametrize("field", list(BASE))
def test_put_requires_complete_record(api_client, field):
    client, path = api_client
    item = insert(client, path)
    body = dict(BASE)
    body.pop(field)
    response = client.put(path + "/" + item["id"], json=body)
    assert response.status_code == 422
    assert client.get(path + "/" + item["id"]).json() == item


@pytest.mark.parametrize("number", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_values_produce_validation_error(api_client, number):
    client, path = api_client
    response = client.post(
        path,
        content=json.dumps({**BASE, "PJME_MW": number}),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 1001},
        {"offset": -1},
        {"offset": 10000001},
        {"limit": "bad"},
    ],
)
def test_invalid_pagination(api_client, params):
    client, path = api_client
    assert client.get(path, params=params).status_code == 422


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"start": BASE["Datetime"]},
        {"start": "bad", "end": BASE["Datetime"]},
        {"start": "2018-01-02T00:00:00", "end": BASE["Datetime"]},
        {"start": "2018-01-01", "end": BASE["Datetime"]},
        {"start": BASE["Datetime"], "end": "2018-01-02T00:00:00Z"},
    ],
)
def test_invalid_range(api_client, params):
    client, path = api_client
    assert client.get(path + "/range", params=params).status_code == 422


def test_malformed_json(api_client):
    client, path = api_client
    response = client.post(path, content="{", headers={"Content-Type": "application/json"})
    assert response.status_code == 422
