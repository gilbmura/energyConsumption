"""One router factory prevents the MySQL and MongoDB contracts from drifting."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from api.app.repositories.base import RecordRepository
from api.app.schemas import RecentRecords, Record, RecordPage, RecordWrite, Timestamp


def build_router(backend: str, dependency) -> APIRouter:
    router = APIRouter(prefix=f"/{backend}/records", tags=[backend])
    repository_type = Annotated[RecordRepository, Depends(dependency)]

    def require_record(record):
        if record is None:
            raise HTTPException(status_code=404, detail="Record not found")
        return record

    @router.post("", response_model=Record, status_code=201)
    def create_record(body: RecordWrite, repository: repository_type, response: Response):
        record = repository.create(body)
        response.headers["Location"] = f"/{backend}/records/{record.id}"
        return record

    @router.get("", response_model=RecordPage)
    def list_records(
        repository: repository_type,
        limit: Annotated[int, Query(ge=1, le=1000)] = 200,
        offset: Annotated[int, Query(ge=0, le=10000000)] = 0,
    ):
        records = repository.list_records(limit + 1, offset)
        return RecordPage(
            items=records[:limit], limit=limit, offset=offset, has_more=len(records) > limit
        )

    @router.get("/recent", response_model=RecentRecords)
    def recent_records(
        repository: repository_type, limit: Annotated[int, Query(ge=1, le=1000)] = 200
    ):
        """Most recent N observations, oldest to newest, for the forecast client."""
        return RecentRecords(records=repository.recent(limit))

    # Literal paths must precede /{record_id}.
    @router.get("/latest", response_model=Record)
    def latest_record(repository: repository_type):
        return require_record(repository.latest())

    @router.get("/range", response_model=RecordPage)
    def records_by_range(
        start: Timestamp,
        end: Timestamp,
        repository: repository_type,
        limit: Annotated[int, Query(ge=1, le=1000)] = 200,
        offset: Annotated[int, Query(ge=0, le=10000000)] = 0,
    ):
        if start > end:
            raise HTTPException(
                status_code=422, detail="start must be earlier than or equal to end"
            )
        records = repository.list_records(limit + 1, offset, start, end)
        return RecordPage(
            items=records[:limit], limit=limit, offset=offset, has_more=len(records) > limit
        )

    @router.get("/{record_id}", response_model=Record)
    def get_record(record_id: str, repository: repository_type):
        return require_record(repository.get(record_id))

    @router.put("/{record_id}", response_model=Record)
    def replace_record(record_id: str, body: RecordWrite, repository: repository_type):
        return require_record(repository.replace(record_id, body))

    @router.delete("/{record_id}", status_code=204)
    def delete_record(record_id: str, repository: repository_type):
        if not repository.delete(record_id):
            raise HTTPException(status_code=404, detail="Record not found")
        return Response(status_code=204)

    return router
