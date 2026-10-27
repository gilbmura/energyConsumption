"""Load the shared cleaned CSV into Laura's real MySQL/MongoDB schema.

Run from the repository root: python -m databases.scripts.load_csv_to_databases
--validate-only requires no database. Writes are upserts in bounded batches.
"""

import argparse
import csv
from itertools import islice
from pathlib import Path

import pymysql
from pymongo import MongoClient, UpdateOne

from databases.config import REPO_ROOT, Settings
from databases.records import Observation
from databases.schema import (
    DIMENSION_SQL,
    LEGACY_FEATURES,
    dimension_values,
    initialize_mongo,
    initialize_mysql,
    observation_document,
    source_id,
)


def read_records(path: Path, limit: int | None = None, tail: bool = False) -> list[Observation]:
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")
    records = []
    seen = set()
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if not set(Observation.model_fields) <= set(reader.fieldnames or []):
            raise ValueError("CSV must contain Datetime, PJME_MW, temperature_c and was_imputed")
        for line, row in enumerate(reader, start=2):
            try:
                flag = row["was_imputed"].strip().lower()
                if flag not in {"true", "false"}:
                    raise ValueError("was_imputed must be True or False")
                record = Observation(
                    Datetime=row["Datetime"],
                    PJME_MW=float(row["PJME_MW"]),
                    temperature_c=float(row["temperature_c"]),
                    was_imputed=flag == "true",
                )
                if record.Datetime in seen:
                    raise ValueError(f"Duplicate timestamp: {record.Datetime}")
                seen.add(record.Datetime)
                records.append(record)
            except (ValueError, KeyError) as exc:
                raise ValueError(f"Invalid CSV record on line {line}: {exc}") from exc
    # Validate the entire source before touching either database.
    records.sort(key=lambda row: row.Datetime)
    return records if limit is None else (records[-limit:] if tail else records[:limit])


def batches(records, size=1000):
    iterator = iter(records)
    while part := list(islice(iterator, size)):
        yield part


def load_mysql(records, settings):
    connection = pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,
        autocommit=False,
    )
    try:
        initialize_mysql(connection, settings.mysql_database)
        for part in batches(records):
            try:
                with connection.cursor() as cursor:
                    sid = source_id(cursor, settings.mysql_source_id)
                    cursor.executemany(
                        DIMENSION_SQL, [dimension_values(row.Datetime) for row in part]
                    )
                    cursor.executemany(
                        "INSERT INTO energy_readings "
                        "(Datetime, PJME_MW, temperature_c, was_imputed, source_id) "
                        "VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE "
                        "PJME_MW=VALUES(PJME_MW), temperature_c=VALUES(temperature_c), "
                        "was_imputed=VALUES(was_imputed), source_id=VALUES(source_id)",
                        [
                            (
                                row.Datetime,
                                row.PJME_MW,
                                row.temperature_c,
                                row.was_imputed,
                                sid,
                            )
                            for row in part
                        ],
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
    finally:
        connection.close()


def load_mongo(records, settings):
    with MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000) as client:
        collection = client[settings.mongo_database][settings.mongo_collection]
        initialize_mongo(collection)
        for part in batches(records):
            collection.bulk_write(
                [
                    UpdateOne(
                        {"Datetime": row.Datetime},
                        {
                            "$set": observation_document(row.model_dump()),
                            "$unset": {field: "" for field in LEGACY_FEATURES},
                        },
                        upsert=True,
                    )
                    for row in part
                ],
                ordered=True,
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=REPO_ROOT / "pjme_clean.csv")
    parser.add_argument("--backend", choices=["mysql", "mongo", "both"], default="both")
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--tail", action="store_true", help="Select the most recent rows with --limit"
    )
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    records = read_records(args.csv, args.limit, args.tail)
    if not records:
        raise ValueError("CSV has no data records")
    print(
        f"Validated source; selected {len(records)} records: "
        f"{records[0].Datetime} through {records[-1].Datetime}"
    )
    if args.validate_only:
        return
    settings = Settings()
    for backend, loader in (("mysql", load_mysql), ("mongo", load_mongo)):
        if args.backend in {backend, "both"}:
            loader(records, settings)
            print(f"{backend}: upserted {len(records)} records")
    print("Finished. Each backend commits independently; rerun after a partial failure.")


if __name__ == "__main__":
    main()
