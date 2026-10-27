"""Driver-boundary checks; real MongoDB is exercised with --live-databases."""

from unittest.mock import MagicMock

import pytest
from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from api.app.repositories.base import DuplicateRecord
from api.app.repositories.mongo_repository import MongoRepository
from api.app.schemas import RecordWrite
from api.tests.test_api import BASE
from databases.schema import LEGACY_FEATURES, calendar_fields


def test_insert_uses_datetime_and_returns_string_id():
    collection = MagicMock()
    record_id = ObjectId()
    collection.insert_one.return_value.inserted_id = record_id
    record = RecordWrite(**BASE)
    result = MongoRepository(collection).create(record)
    assert result.id == str(record_id)
    assert collection.insert_one.call_args.args[0]["Datetime"] == record.Datetime


def test_duplicate_insert_maps_to_conflict():
    collection = MagicMock()
    collection.insert_one.side_effect = DuplicateKeyError("duplicate")
    with pytest.raises(DuplicateRecord):
        MongoRepository(collection).create(RecordWrite(**BASE))


def test_update_preserves_unrelated_fields_and_returns_updated_record():
    collection = MagicMock()
    record_id = ObjectId()
    record = RecordWrite(**BASE)
    collection.find_one_and_update.return_value = {
        "_id": record_id,
        **record.model_dump(),
        "teammate_metadata": "preserve",
    }
    result = MongoRepository(collection).replace(str(record_id), record)
    assert result.id == str(record_id)
    args, kwargs = collection.find_one_and_update.call_args
    assert args == (
        {"_id": record_id},
        {
            "$set": {**record.model_dump(), **calendar_fields(record.Datetime)},
            "$unset": {field: "" for field in LEGACY_FEATURES},
        },
    )
    assert kwargs["return_document"] == ReturnDocument.AFTER
    assert "teammate_metadata" not in result.model_dump()
