"""Transactional CRUD against Laura's time_dimensions and energy_readings tables."""

from datetime import datetime

import pymysql

from api.app.config import Settings
from api.app.repositories.base import DuplicateRecord, InvalidRecordId
from api.app.schemas import Record, RecordWrite
from databases.schema import DIMENSION_SQL, dimension_values, source_id

SELECT_FIELDS = "reading_id AS id, Datetime, PJME_MW, was_imputed, temperature_c"


class MySQLRepository:
    def __init__(self, connection, settings: Settings):
        self.connection = connection
        self.settings = settings

    @staticmethod
    def _id(record_id: str) -> int:
        if not record_id.isascii() or not record_id.isdecimal() or len(record_id) > 19:
            raise InvalidRecordId("MySQL IDs must be positive integers")
        value = int(record_id)
        if not 1 <= value <= 9223372036854775807:
            raise InvalidRecordId("MySQL ID is outside the supported range")
        return value

    @staticmethod
    def _record(row) -> Record | None:
        if row is None:
            return None
        return Record(**{**row, "id": str(row["id"]), "was_imputed": bool(row["was_imputed"])})

    def _rollback(self, exc):
        self.connection.rollback()
        if isinstance(exc, pymysql.IntegrityError) and exc.args[0] == 1062:
            raise DuplicateRecord from exc
        raise exc

    def create(self, record: RecordWrite) -> Record:
        try:
            with self.connection.cursor() as cursor:
                sid = source_id(cursor, self.settings.mysql_source_id)
                cursor.execute(DIMENSION_SQL, dimension_values(record.Datetime))
                cursor.execute(
                    "INSERT INTO energy_readings "
                    "(Datetime, PJME_MW, was_imputed, temperature_c, source_id) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (
                        record.Datetime,
                        record.PJME_MW,
                        record.was_imputed,
                        record.temperature_c,
                        sid,
                    ),
                )
                record_id = cursor.lastrowid
            self.connection.commit()
        except Exception as exc:
            self._rollback(exc)
        return Record(id=str(record_id), **record.model_dump())

    def get(self, record_id: str) -> Record | None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {SELECT_FIELDS} FROM energy_readings WHERE reading_id=%s",
                (self._id(record_id),),
            )
            return self._record(cursor.fetchone())

    def replace(self, record_id: str, record: RecordWrite) -> Record | None:
        value = self._id(record_id)
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT reading_id FROM energy_readings WHERE reading_id=%s FOR UPDATE",
                    (value,),
                )
                if cursor.fetchone() is None:
                    self.connection.rollback()
                    return None
                # Create/reuse the new calendar key; do not move the parent key via CASCADE.
                cursor.execute(DIMENSION_SQL, dimension_values(record.Datetime))
                cursor.execute(
                    "UPDATE energy_readings SET Datetime=%s, PJME_MW=%s, was_imputed=%s, "
                    "temperature_c=%s WHERE reading_id=%s",
                    (
                        record.Datetime,
                        record.PJME_MW,
                        record.was_imputed,
                        record.temperature_c,
                        value,
                    ),
                )
            self.connection.commit()
        except Exception as exc:
            self._rollback(exc)
        return Record(id=str(value), **record.model_dump())

    def delete(self, record_id: str) -> bool:
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM energy_readings WHERE reading_id=%s", (self._id(record_id),)
                )
                deleted = cursor.rowcount > 0
            # Calendar/provenance dimensions are retained; only the requested observation is removed.
            self.connection.commit()
            return deleted
        except Exception as exc:
            self._rollback(exc)

    def latest(self) -> Record | None:
        records = self.recent(1)
        return records[0] if records else None

    def recent(self, limit: int) -> list[Record]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {SELECT_FIELDS} FROM energy_readings "
                "ORDER BY Datetime DESC, reading_id DESC LIMIT %s",
                (limit,),
            )
            return list(reversed([self._record(row) for row in cursor.fetchall()]))

    def list_records(
        self, limit: int, offset: int, start: datetime | None = None, end: datetime | None = None
    ) -> list[Record]:
        where = " WHERE Datetime >= %s AND Datetime <= %s" if start is not None else ""
        params = (start, end, limit, offset) if start is not None else (limit, offset)
        with self.connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {SELECT_FIELDS} FROM energy_readings{where} "
                "ORDER BY Datetime ASC, reading_id ASC LIMIT %s OFFSET %s",
                params,
            )
            return [self._record(row) for row in cursor.fetchall()]
