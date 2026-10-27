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
try:
    from .features import make_next_features
except ImportError:  # Direct script execution remains supported.
    from features import make_next_features

ROOT = Path(__file__).resolve().parents[1]


def get_records(url=None, mock=False):
    if mock:
        raw = pd.read_csv(ROOT.parent / 'pjme_clean.csv')
        raw['Datetime'] = pd.to_datetime(raw['Datetime'], errors='raise')
        raw = raw.sort_values('Datetime').tail(200).copy()
        raw['Datetime'] = raw['Datetime'].astype(str)
        return raw[['Datetime', 'PJME_MW', 'was_imputed']].to_dict(orient='records')
    if not url:
        raise ValueError('Supply --api-url or --mock')
    with urlopen(url, timeout=20) as response:
        payload = json.load(response)
    if isinstance(payload, dict):
        if payload.get('has_more'):
            raise ValueError('Use /mysql/records/recent or /mongo/records/recent for complete recent history')
        payload = payload.get('records', payload.get('items', payload.get('data')))
    if not isinstance(payload, list):
        raise ValueError('API must return a list or an object containing a records/items/data list')
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
