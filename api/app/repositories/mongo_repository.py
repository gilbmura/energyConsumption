"""MongoDB adapter; BSON datetimes preserve the agreed naive dataset clock labels."""

from datetime import datetime

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from api.app.repositories.base import DuplicateRecord, InvalidRecordId
from api.app.schemas import Record, RecordWrite
from databases.schema import LEGACY_FEATURES, calendar_fields, observation_document


class MongoRepository:
    def __init__(self, collection):
        self.collection = collection

    @staticmethod
    def _id(record_id: str) -> ObjectId:
        if not ObjectId.is_valid(record_id):
            raise InvalidRecordId("MongoDB IDs must be 24 hexadecimal characters")
        return ObjectId(record_id)

    @staticmethod
    def _record(document) -> Record | None:
        if document is None:
            return None
        return Record(
            id=str(document["_id"]),
            **{key: document[key] for key in RecordWrite.model_fields},
        )

    def create(self, record: RecordWrite) -> Record:
        document = observation_document(record.model_dump())
        try:
            result = self.collection.insert_one(document)
        except DuplicateKeyError as exc:
            raise DuplicateRecord from exc
        return Record(id=str(result.inserted_id), **record.model_dump())

    def get(self, record_id: str) -> Record | None:
        return self._record(self.collection.find_one({"_id": self._id(record_id)}))

    def replace(self, record_id: str, record: RecordWrite) -> Record | None:
        try:
            # Replace the public record fields; preserve teammate-owned metadata.
            document = self.collection.find_one_and_update(
                {"_id": self._id(record_id)},
                {
                    "$set": {**record.model_dump(), **calendar_fields(record.Datetime)},
                    "$unset": {field: "" for field in LEGACY_FEATURES},
                },
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError as exc:
            raise DuplicateRecord from exc
        return self._record(document)

    def delete(self, record_id: str) -> bool:
        return self.collection.delete_one({"_id": self._id(record_id)}).deleted_count == 1

    def latest(self) -> Record | None:
        return self._record(self.collection.find_one(sort=[("Datetime", -1), ("_id", -1)]))

    def recent(self, limit: int) -> list[Record]:
        cursor = self.collection.find().sort([("Datetime", -1), ("_id", -1)]).limit(limit)
        return list(reversed([self._record(document) for document in cursor]))

    def list_records(
        self, limit: int, offset: int, start: datetime | None = None, end: datetime | None = None
    ) -> list[Record]:
        query = {"Datetime": {"$gte": start, "$lte": end}} if start is not None else {}
        cursor = (
            self.collection.find(query)
            .sort([("Datetime", 1), ("_id", 1)])
            .skip(offset)
            .limit(limit)
        )
        return [self._record(document) for document in cursor]
