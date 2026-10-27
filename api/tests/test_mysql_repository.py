"""Driver-boundary tests; only --live-databases tests prove actual MySQL behavior."""

from unittest.mock import MagicMock

import pymysql
import pytest

from api.app.config import Settings
from api.app.repositories.base import DuplicateRecord
from api.app.repositories.mysql_repository import MySQLRepository
from api.app.schemas import RecordWrite
from api.tests.test_api import BASE


def repository():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.lastrowid = 42
    cursor.fetchone.return_value = {"source_id": 7, "reading_id": 42}
    return MySQLRepository(connection, Settings(_env_file=None)), connection, cursor


def test_insert_binds_values_and_commits():
    repo, connection, cursor = repository()
    record = RecordWrite(**BASE)
    assert repo.create(record).id == "42"
    sql, parameters = cursor.execute.call_args.args
    assert "VALUES (%s, %s, %s, %s, %s)" in sql
    assert parameters == (
        record.Datetime,
        record.PJME_MW,
        record.was_imputed,
        record.temperature_c,
        7,
    )
    connection.commit.assert_called_once()


def test_insert_duplicate_rolls_back():
    repo, connection, cursor = repository()
    cursor.execute.side_effect = [None, None, pymysql.IntegrityError(1062, "duplicate")]
    with pytest.raises(DuplicateRecord):
        repo.create(RecordWrite(**BASE))
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()


def test_foreign_key_error_is_not_mislabeled_as_duplicate():
    repo, connection, cursor = repository()
    cursor.execute.side_effect = pymysql.IntegrityError(1452, "foreign key")
    with pytest.raises(pymysql.IntegrityError):
        repo.create(RecordWrite(**BASE))
    connection.rollback.assert_called_once()


def test_unchanged_put_is_successful_even_when_rowcount_is_zero():
    repo, connection, cursor = repository()
    cursor.fetchone.return_value = {"id": 42}
    cursor.rowcount = 0
    assert repo.replace("42", RecordWrite(**BASE)).id == "42"
    connection.commit.assert_called_once()


def test_update_failure_rolls_back_transaction():
    repo, connection, cursor = repository()
    cursor.fetchone.return_value = {"id": 42}
    cursor.execute.side_effect = [None, pymysql.OperationalError(1205, "timeout")]
    with pytest.raises(pymysql.OperationalError):
        repo.replace("42", RecordWrite(**BASE))
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()
