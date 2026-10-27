"""Provision Laura's canonical schema; never substitute a second SQL design."""

import re
from pathlib import Path

import pymysql

DATASET_NAME = "Hourly Energy Consumption - PJME (Cleaned Multivariate)"
PROVIDER = "Kaggle collection by Rob Mulla & Group Preprocessing"
LEGACY_FEATURES = ("lag_1", "lag_24", "lag_168", "rolling_mean_24", "rolling_mean_168")


def schema_statements():
    """The checked-in DDL contains simple statements without embedded semicolons."""
    sql = (Path(__file__).parent / "mysql" / "schema.sql").read_text(encoding="utf-8-sig")
    sql = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
    return [
        part.strip()
        for part in sql.split(";")
        if part.strip() and not part.strip().upper().startswith(("CREATE DATABASE", "USE "))
    ]


def initialize_mysql(connection, database):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", database):
        raise ValueError("Invalid database identifier")
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4")
        cursor.execute(f"USE `{database}`")
        for statement in schema_statements():
            cursor.execute(statement)
        cursor.execute("SHOW COLUMNS FROM energy_readings")
        rows = cursor.fetchall()
        columns = {row["Field"] if isinstance(row, dict) else row[0] for row in rows}
        required = {
            "reading_id",
            "Datetime",
            "PJME_MW",
            "temperature_c",
            "was_imputed",
            "source_id",
        }
        if not required <= columns:
            raise RuntimeError(
                "Existing energy_readings uses an incompatible older schema. "
                "Back up and migrate it before loading; no tables were dropped."
            )
    connection.commit()


def initialize_mongo(collection):
    indexes = [
        ([("Datetime", 1)], "uniq_datetime", True),
        ([("Datetime", 1), ("PJME_MW", 1)], "compound_datetime_demand", False),
        ([("hour", 1)], "idx_hour", False),
        ([("temperature_c", 1)], "idx_temperature", False),
    ]
    existing = list(collection.index_information().values())
    for keys, name, unique in indexes:
        matches = [index for index in existing if list(index["key"]) == keys]
        if matches:
            if unique and not matches[0].get("unique", False):
                raise ValueError(
                    "Datetime has a non-unique index; migrate it explicitly before loading"
                )
            continue
        collection.create_index(keys, name=name, unique=unique)


def source_id(cursor, configured_id=None):
    if configured_id is None:
        cursor.execute(
            "SELECT source_id FROM data_sources WHERE dataset_name=%s AND provider=%s",
            (DATASET_NAME, PROVIDER),
        )
    else:
        cursor.execute("SELECT source_id FROM data_sources WHERE source_id=%s", (configured_id,))
    row = cursor.fetchone()
    if row is None:
        raise pymysql.OperationalError(1644, "Initialize the canonical data source before writing")
    return int(row["source_id"] if isinstance(row, dict) else row[0])


def calendar_fields(timestamp):
    return {
        "hour": timestamp.hour,
        "day_of_week": timestamp.weekday(),
        "month": timestamp.month,
        "is_weekend": timestamp.weekday() >= 5,
    }


DIMENSION_SQL = (
    "INSERT INTO time_dimensions (Datetime, hour, day_of_week, month, is_weekend) "
    "VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE "
    "hour=VALUES(hour), day_of_week=VALUES(day_of_week), "
    "month=VALUES(month), is_weekend=VALUES(is_weekend)"
)


def dimension_values(timestamp):
    fields = calendar_fields(timestamp)
    return (
        timestamp,
        fields["hour"],
        fields["day_of_week"],
        fields["month"],
        fields["is_weekend"],
    )


def observation_document(record):
    return {**record, **calendar_fields(record["Datetime"]), "source": "PJME_clean"}
