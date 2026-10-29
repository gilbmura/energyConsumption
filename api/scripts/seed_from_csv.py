"""Import a validated sample through the API, preserving existing timestamps."""

import argparse
from pathlib import Path

import httpx

from databases.config import REPO_ROOT
from databases.scripts.load_csv_to_databases import read_records


def load_records(path: Path, limit: int, tail: bool = False):
    return read_records(path, limit=limit, tail=tail)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=REPO_ROOT / "pjme_clean.csv")
    parser.add_argument("--backend", choices=["mysql", "mongo"], required=True)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument(
        "--tail", action="store_true", help="Load latest rows for the forecast demo"
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    records = load_records(args.csv, args.limit, args.tail)
    created = duplicates = 0
    with httpx.Client(base_url=args.base_url, timeout=15) as client:
        for record in records:
            response = client.post(f"/{args.backend}/records", json=record.model_dump(mode="json"))
            if response.status_code == 409:
                duplicates += 1
            else:
                response.raise_for_status()
                created += 1
    print(f"Created: {created}; existing timestamps skipped without comparing values: {duplicates}")


if __name__ == "__main__":
    main()
