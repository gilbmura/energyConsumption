"""Make a one-hour-ahead forecast using the API or local dataset as a mock.

API GET payload can be either a JSON array or {'records': [...]}.
Each record: {'Datetime': '2018-08-02T23:00:00', 'PJME_MW': 35000.0}.
At least 168 CONSECUTIVE hours leading to latest timestamp are required.
"""
import argparse
import json
from pathlib import Path
from urllib.request import urlopen

import joblib
import pandas as pd
from features import make_next_features, to_hourly_series

ROOT = Path(__file__).resolve().parents[1]


def get_records(url=None, mock=False):
    if mock:
        raw = pd.read_csv(ROOT.parent / 'pjme_clean.csv')
        series = to_hourly_series(raw)
        # For testing only; simulates 200 records supplied by an API.
        return [
            {'Datetime': str(timestamp), 'PJME_MW': float(value)}
            for timestamp, value in series.tail(200).items()
        ]
    if not url:
        raise ValueError('Supply --api-url or --mock')
    with urlopen(url, timeout=20) as response:
        payload = json.load(response)
    if isinstance(payload, dict):
        payload = payload.get('records', payload.get('data'))
    if not isinstance(payload, list):
        raise ValueError('API must return a list or an object containing a records/data list')
    return payload


def forecast(records, artifact):
    next_time, features = make_next_features(records)
    columns = artifact['features']
    model_features = pd.DataFrame([features], columns=columns)
    demand = float(artifact['model'].predict(model_features)[0])
    return next_time, round(demand, 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--api-url', help='URL returning the last 168+ hourly PJME observations as JSON')
    source.add_argument('--mock', action='store_true', help='Test with historical data, no API required')
    args = parser.parse_args()
    artifact = joblib.load(ROOT / 'models' / 'pjme_forecast.joblib')
    next_time, predicted = forecast(get_records(args.api_url, args.mock), artifact)
    print(json.dumps({
        'forecast_for': str(next_time),
        'predicted_PJME_MW': predicted,
        'source': 'mock local records' if args.mock else args.api_url,
    }, indent=2))


if __name__ == '__main__':
    main()
