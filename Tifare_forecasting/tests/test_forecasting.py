"""Tests for time-series feature consistency, data quality, and HTTP input."""
import json
import sys
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from features import FEATURES, make_feature_frame, make_next_features, to_hourly_series
from predict import get_records, forecast


class ForecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = pd.read_csv(ROOT.parent / 'pjme_clean.csv')
        cls.hourly = to_hourly_series(cls.data)
        cls.artifact = joblib.load(ROOT / 'models' / 'pjme_forecast.joblib')
        latest = cls.hourly.tail(200)
        cls.records = [
            {'Datetime': str(t), 'PJME_MW': float(x)}
            for t, x in latest.items()
        ]

    def test_shared_features_match_training(self):
        """Forecast features for time t must exactly equal supervised row t."""
        t = self.hourly.index[-1]
        history = self.hourly.loc[:t].iloc[-169:-1]
        records = [{'Datetime': str(timestamp), 'PJME_MW': value} for timestamp, value in history.items()]
        timestamp, features = make_next_features(records)
        self.assertEqual(timestamp, t)
        expected = make_feature_frame(self.hourly).loc[t, FEATURES]
        for key in FEATURES:
            self.assertAlmostEqual(features[key], float(expected[key]), places=8, msg=key)

    def test_unordered_records_still_forecast(self):
        t, features = make_next_features(self.records[::-1])
        self.assertEqual(t, self.hourly.index.max() + pd.Timedelta(hours=1))
        self.assertGreater(features['lag_1'], 0)

    def test_missing_history_rejected(self):
        with self.assertRaisesRegex(ValueError, '168 consecutive'):
            make_next_features(self.records[-50:])
        bad = [r for r in self.records if r['Datetime'] != self.records[-10]['Datetime']]
        with self.assertRaisesRegex(ValueError, '168 consecutive'):
            make_next_features(bad)

    def test_imputed_data_is_excluded(self):
        """The shared CSV flags 30 interpolated values, which must be masked."""
        self.assertEqual(self.hourly.isna().sum(), 30)
        imputed = self.data[self.data["was_imputed"].astype(str).str.lower().eq("true")].iloc[0]
        self.assertTrue(pd.isna(self.hourly.loc[pd.Timestamp(imputed["Datetime"])]))

    def test_http_api_integration_with_local_stub(self):
        """Use actual HTTP GET + JSON decoding, not the --mock shortcut."""
        records = self.records

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = json.dumps({'records': records}).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                return

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            actual = get_records(url=f'http://127.0.0.1:{server.server_port}/records')
            timestamp, predicted = forecast(actual, self.artifact)
            self.assertEqual(timestamp, self.hourly.index.max() + pd.Timedelta(hours=1))
            self.assertGreater(predicted, 0)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == '__main__':
    unittest.main()
