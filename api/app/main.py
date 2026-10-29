import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from pymysql import MySQLError

from api.app.config import Settings
from api.app.dependencies import get_mongo_repository, get_mysql_repository
from api.app.repositories.base import DuplicateRecord, InvalidRecordId
from api.app.routes.records import build_router

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Lazy connection lets each database remain usable if the other is offline.
        app.state.mongo_client = MongoClient(
            settings.mongo_uri,
            connect=False,
            tz_aware=False,
            serverSelectionTimeoutMS=3000,
            connectTimeoutMS=3000,
            socketTimeoutMS=10000,
        )
        try:
            yield
        finally:
            app.state.mongo_client.close()

    app = FastAPI(title="PJME Energy API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings

    @app.exception_handler(DuplicateRecord)
    async def duplicate_handler(request: Request, exc: DuplicateRecord):
        return JSONResponse(
            status_code=409, content={"detail": "A record already exists at this Datetime"}
        )

    @app.exception_handler(InvalidRecordId)
    async def invalid_id_handler(request: Request, exc: InvalidRecordId):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        # Do not echo non-finite numbers, request data, or exception objects into JSON.
        errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors})

    async def database_handler(request: Request, exc: Exception):
        logger.error("Database request failed: %s", type(exc).__name__)
        return JSONResponse(
            status_code=503, content={"detail": "Database unavailable or not configured"}
        )

    app.add_exception_handler(MySQLError, database_handler)
    app.add_exception_handler(PyMongoError, database_handler)
    app.include_router(build_router("mysql", get_mysql_repository))
    app.include_router(build_router("mongo", get_mongo_repository))

    @app.get("/health", tags=["health"])
    def health():
        """Process liveness only; does not claim that either database is ready."""
        return {"status": "ok", "database_readiness": "not_checked"}

    return app


app = create_app()
