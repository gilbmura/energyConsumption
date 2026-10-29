"""HTTP response envelopes over the shared dataset contract."""

from pydantic import BaseModel

from databases.records import Observation, Timestamp


class RecordWrite(Observation):
    pass


class Record(RecordWrite):
    id: str


class RecordPage(BaseModel):
    items: list[Record]
    limit: int
    offset: int
    has_more: bool


class RecentRecords(BaseModel):
    records: list[Record]


__all__ = ["RecordWrite", "Record", "RecordPage", "RecentRecords", "Timestamp"]
