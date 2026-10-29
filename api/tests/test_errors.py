"""Database failures must not leak connection details into HTTP responses."""

import pytest
from fastapi.testclient import TestClient
from pymongo.errors import ServerSelectionTimeoutError
from pymysql import OperationalError

from api.app.config import Settings
from api.app.dependencies import get_mongo_repository, get_mysql_repository
from api.app.main import create_app


@pytest.mark.parametrize(
    "backend, dependency, error",
    [
        ("mysql", get_mysql_repository, OperationalError(2003, "secret-password")),
        ("mongo", get_mongo_repository, ServerSelectionTimeoutError("secret-password")),
    ],
)
def test_database_unavailable_returns_sanitized_503(backend, dependency, error):
    app = create_app(Settings(_env_file=None))

    def fail():
        raise error

    app.dependency_overrides[dependency] = fail
    with TestClient(app) as client:
        response = client.get(f"/{backend}/records/latest")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable or not configured"}
    assert "secret-password" not in response.text


def test_health_and_openapi_do_not_require_databases():
    with TestClient(create_app(Settings(_env_file=None))) as client:
        assert client.get("/health").json()["database_readiness"] == "not_checked"
        schema = client.get("/openapi.json").json()
        for backend in ("mysql", "mongo"):
            assert set(schema["paths"][f"/{backend}/records"]) == {"get", "post"}
            assert set(schema["paths"][f"/{backend}/records/{{record_id}}"]) == {
                "get",
                "put",
                "delete",
            }
            assert "get" in schema["paths"][f"/{backend}/records/latest"]
            assert "get" in schema["paths"][f"/{backend}/records/range"]
