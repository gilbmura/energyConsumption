"""Run the same HTTP behavior tests against doubles or real databases.

--live-databases creates random, dedicated test databases and removes only those
databases afterwards. It never points at the group's dataset or development rows.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import mongomock
import pymysql
import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from api.app.config import Settings
from api.app.dependencies import get_mongo_repository, get_mysql_repository
from api.app.main import create_app
from api.app.repositories.mongo_repository import MongoRepository
from api.tests.fakes import MemoryRepository
from databases.schema import initialize_mongo, initialize_mysql


def pytest_addoption(parser):
    parser.addoption(
        "--live-databases", action="store_true", help="Exercise real MySQL and MongoDB"
    )


@pytest.fixture(scope="session")
def live_settings(request):
    if not request.config.getoption("--live-databases"):
        yield None
        return
    database = "energy_api_test_" + uuid.uuid4().hex
    settings = Settings(
        _env_file=None,
        mysql_host=os.getenv("TEST_MYSQL_HOST", "127.0.0.1"),
        mysql_port=int(os.getenv("TEST_MYSQL_PORT", "3307")),
        mysql_user=os.getenv("TEST_MYSQL_USER", "root"),
        mysql_password=os.getenv("TEST_MYSQL_PASSWORD", "local_root_password"),
        mysql_database=database,
        mongo_uri=os.getenv("TEST_MONGO_URI", "mongodb://127.0.0.1:27018"),
        mongo_database=database,
    )
    connection = pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        connect_timeout=5,
        autocommit=True,
    )
    mongo = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=3000)
    created_mysql = False
    created_mongo = False
    try:
        mongo.admin.command("ping")
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{database}`")
            created_mysql = True
            cursor.execute(f"USE `{database}`")
        initialize_mysql(connection, database)
        initialize_mongo(mongo[database][settings.mongo_collection])
        created_mongo = True
        yield settings
    finally:
        # The name is generated above, never taken from user-supplied configuration.
        assert database.startswith("energy_api_test_") and len(database) == 48
        if created_mysql:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{database}`")
        if created_mongo:
            mongo.drop_database(database)
        connection.close()
        mongo.close()


@pytest.fixture(params=["mysql", "mongo"])
def backend(request):
    return request.param


@pytest.fixture
def api_client(backend, live_settings, request, http_evidence):
    settings = live_settings or Settings(_env_file=None)
    app = create_app(settings)
    if live_settings:
        if backend == "mysql":
            connection = pymysql.connect(
                host=settings.mysql_host,
                port=settings.mysql_port,
                user=settings.mysql_user,
                password=settings.mysql_password,
                database=settings.mysql_database,
                autocommit=True,
            )
            try:
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM energy_readings")
                    cursor.execute("DELETE FROM time_dimensions")
            finally:
                connection.close()
        else:
            with MongoClient(settings.mongo_uri) as mongo:
                mongo[settings.mongo_database][settings.mongo_collection].delete_many({})
    else:
        dependency = get_mysql_repository if backend == "mysql" else get_mongo_repository
        if backend == "mongo":
            collection = mongomock.MongoClient().pjme_energy.energy_observations
            initialize_mongo(collection)
            repository = MongoRepository(collection)
        else:
            repository = MemoryRepository(backend)
        app.dependency_overrides[dependency] = lambda: repository
    with TestClient(app) as client:

        def capture(response):
            response.read()
            http_evidence.append(
                {
                    "test": request.node.name,
                    "backend": backend,
                    "method": response.request.method,
                    "url": str(response.request.url),
                    "request_body": response.request.content.decode("utf-8", errors="replace"),
                    "status": response.status_code,
                    "response_body": response.text,
                }
            )

        client.event_hooks["response"].append(capture)
        yield client, f"/{backend}/records"


@pytest.fixture(scope="session")
def http_evidence(request):
    entries = []
    yield entries
    live = request.config.getoption("--live-databases")
    mode = "live" if live else "unit"
    target = Path(__file__).parents[1] / "evidence" / f"http-{mode}.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "mode": "real MySQL and MongoDB"
                if live
                else "SQL repository double and mongomock; not real databases",
                "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                "requests": entries,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
