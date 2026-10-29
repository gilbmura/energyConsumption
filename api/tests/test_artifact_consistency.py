"""Check the committed model against its saved held-out predictions and metrics."""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from Tifare_forecasting.scripts.features import FEATURES, make_feature_frame, to_hourly_series

ROOT = Path(__file__).resolve().parents[2]


def test_saved_model_predictions_and_metrics_are_consistent():
    folder = ROOT / "Tifare_forecasting"
    artifact = joblib.load(folder / "models/pjme_forecast.joblib")
    assert artifact["features"] == FEATURES
    source = pd.read_csv(ROOT / "pjme_clean.csv")
    frame = make_feature_frame(to_hourly_series(source)).dropna(subset=["target"] + FEATURES)
    testing = frame.iloc[int(len(frame) * 0.85) :]
    predicted = artifact["model"].predict(testing[FEATURES])
    saved = pd.read_csv(folder / "outputs/test_predictions.csv")
    assert list(pd.to_datetime(saved["Datetime"])) == list(testing.index)
    np.testing.assert_allclose(saved["actual_MW"], testing["target"])
    np.testing.assert_allclose(saved["predicted_MW"], predicted, rtol=1e-10)
    actual_metrics = {
        "MAE": round(float(mean_absolute_error(testing["target"], predicted)), 3),
        "RMSE": round(float(np.sqrt(mean_squared_error(testing["target"], predicted))), 3),
        "R2": round(float(r2_score(testing["target"], predicted)), 5),
    }
    stored = json.loads((folder / "outputs/metrics.json").read_text())
    assert stored["test_metrics"] == actual_metrics
