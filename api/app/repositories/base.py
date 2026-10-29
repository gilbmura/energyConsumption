from datetime import datetime
from typing import Protocol

from api.app.schemas import Record, RecordWrite


class DuplicateRecord(Exception):
    """The provisional single-series contract permits one record per timestamp."""


class InvalidRecordId(Exception):
    """An ID is not valid for the selected database."""


class RecordRepository(Protocol):
    def create(self, record: RecordWrite) -> Record: ...
    def get(self, record_id: str) -> Record | None: ...
    def replace(self, record_id: str, record: RecordWrite) -> Record | None: ...
    def delete(self, record_id: str) -> bool: ...
    def latest(self) -> Record | None: ...
    def recent(self, limit: int) -> list[Record]: ...
    def list_records(
        self,
        limit: int,
        offset: int,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Record]: ...
