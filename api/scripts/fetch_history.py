"""Fetch an ordered, contiguous history window for a teammate's forecasting script.

This helper does not engineer features or load the model: those remain Task 1/4
responsibilities. The returned fields retain the training-data column names.
"""

import argparse
import json
from datetime import datetime, timedelta

import httpx


def fetch_history(base_url: str, backend: str, hours: int = 168) -> list[dict]:
    if backend not in {"mysql", "mongo"} or not 1 <= hours <= 10000:
        raise ValueError("Choose mysql or mongo and between 1 and 10000 history hours")
    with httpx.Client(base_url=base_url, timeout=15) as client:
        latest_response = client.get(f"/{backend}/records/latest")
        latest_response.raise_for_status()
        latest = latest_response.json()
        end = datetime.fromisoformat(latest["Datetime"])
        start = end - timedelta(hours=hours - 1)
        records = []
        while True:
            response = client.get(
                f"/{backend}/records/range",
                params={
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "limit": min(hours, 1000),
                    "offset": len(records),
                },
            )
            response.raise_for_status()
            page = response.json()
            records.extend(page["items"])
            if not page["has_more"]:
                break
            if not page["items"]:
                raise ValueError("API returned an empty page with has_more=true")
    timestamps = [datetime.fromisoformat(row["Datetime"]) for row in records]
    expected = [start + timedelta(hours=index) for index in range(hours)]
    if timestamps != expected:
        raise ValueError(
            f"Expected {hours} consecutive hourly readings; received incomplete history"
        )
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["mysql", "mongo"], required=True)
    parser.add_argument("--hours", type=int, default=168)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    print(json.dumps(fetch_history(args.base_url, args.backend, args.hours), indent=2))


if __name__ == "__main__":
    main()
