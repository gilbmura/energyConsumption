"""In-memory test double only. These tests do not prove database persistence."""

from api.app.repositories.base import DuplicateRecord
from api.app.repositories.mongo_repository import MongoRepository
from api.app.repositories.mysql_repository import MySQLRepository
from api.app.schemas import Record


class MemoryRepository:
    def __init__(self, backend):
        self.backend = backend
        self.records = {}
        self.next_id = 1

    def _id(self, value):
        parser = MySQLRepository._id if self.backend == "mysql" else MongoRepository._id
        return str(parser(value))

    def create(self, record):
        if any(item.Datetime == record.Datetime for item in self.records.values()):
            raise DuplicateRecord
        key = str(self.next_id) if self.backend == "mysql" else f"{self.next_id:024x}"
        self.next_id += 1
        item = Record(id=key, **record.model_dump())
        self.records[key] = item
        return item

    def get(self, record_id):
        return self.records.get(self._id(record_id))

    def replace(self, record_id, record):
        key = self._id(record_id)
        if key not in self.records:
            return None
        if any(
            item.id != key and item.Datetime == record.Datetime for item in self.records.values()
        ):
            raise DuplicateRecord
        item = Record(id=key, **record.model_dump())
        self.records[key] = item
        return item

    def delete(self, record_id):
        return self.records.pop(self._id(record_id), None) is not None

    def latest(self):
        return max(self.records.values(), key=lambda item: item.Datetime, default=None)

    def recent(self, limit):
        return sorted(self.records.values(), key=lambda item: item.Datetime)[-limit:]

    def list_records(self, limit, offset, start=None, end=None):
        rows = sorted(self.records.values(), key=lambda item: item.Datetime)
        if start is not None:
            rows = [row for row in rows if start <= row.Datetime <= end]
        return rows[offset : offset + limit]
