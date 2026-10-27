"""Execute Laura's analytical queries on real MySQL and MongoDB servers.

Run from the repository root with -m databases.scripts.execute_queries_and_export_results.
No SQLite/pandas fallback is used. Output is written only after BOTH servers succeed.
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pymysql
from pymongo import MongoClient

from databases.config import REPO_ROOT, Settings
from databases.queries import NAMES, mongo_queries


def sql_queries():
    text = (REPO_ROOT / "databases/mysql/queries.sql").read_text(encoding="utf-8-sig")
    text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("--"))
    queries = [s.strip() for s in text.split(";") if s.strip() and not s.strip().startswith("USE ")]
    if len(queries) != len(NAMES):
        raise ValueError("Update the query names when adding or removing analytical SQL queries")
    return dict(zip(NAMES, queries, strict=True))


def collect_results(settings):
    report = {
        "mode": "real MySQL and MongoDB",
        "recorded_at_utc": datetime.now(UTC).isoformat(),
    }
    connection = pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION() AS version")
            report["mysql_version"] = cursor.fetchone()["version"]
            report["mysql"] = {}
            for name, query in sql_queries().items():
                cursor.execute(query)
                report["mysql"][name] = {
                    "query": query,
                    "results": list(cursor.fetchall()),
                }
            cursor.execute("SELECT COUNT(*) AS records FROM energy_readings")
            report["mysql_records"] = cursor.fetchone()["records"]
    finally:
        connection.close()
    with MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000) as client:
        report["mongo_version"] = client.server_info()["version"]
        collection = client[settings.mongo_database][settings.mongo_collection]
        report["mongo"] = {}
        for name, pipeline in mongo_queries().items():
            report["mongo"][name] = {
                "pipeline": pipeline,
                "results": list(collection.aggregate(pipeline)),
            }
        report["mongo_records"] = collection.count_documents({})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "databases/results/live_query_results.json",
    )
    args = parser.parse_args()
    report = collect_results(Settings())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(report, indent=2, default=str, allow_nan=False), encoding="utf-8"
    )
    temporary.replace(args.output)
    print(f"Saved actual database queries and responses to {args.output}")


if __name__ == "__main__":
    main()
