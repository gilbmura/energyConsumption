# Member 2: Hourly Electricity Demand Forecasting

**Group assignment:** Working with Time Series Data  
**Dataset:** [Kaggle Hourly Energy Consumption](https://www.kaggle.com/datasets/robikscube/hourly-energy-consumption), using the **shared group CSV** `pjme_clean.csv`  
**Prediction target:** `PJME_MW` at the **next hourly timestamp**.

## What this project implements

- **Task 1C**: supervised forecasting, chronological data split, three explicit hyperparameter experiments, baseline comparisons, held-out test evaluation, visualized predictions and saved model.
- **Task 4, independent portion**: fetch a JSON time series from an HTTP API (or mock local historical readings), use exactly the same feature-engineering method as during training, load the saved model and produce a next-hour forecast.
- Automated checks, including a test that fetches records over HTTP from a local test server.

> **Integration status:** The client is tested with a simulated HTTP API and local data. The *group's actual Member 4 endpoint* has **not** been tested. Connect and test it once available, then show that result in the shared PDF report.

## Folder guide

```text
member2_forecasting/
  ../pjme_clean.csv               Shared group data (already on main)
  scripts/features.py             Shared training/inference feature construction
  scripts/train.py                Model selection, evaluation, artifacts and chart
  scripts/predict.py              Forecast using HTTP JSON API or local mock
  tests/test_forecasting.py       Five automated tests, including HTTP test
  models/pjme_forecast.joblib     Trained model bundle
  outputs/experiments.csv         Three validation experiments
  outputs/metrics.json           Final test and baseline statistics
  outputs/test_predictions.csv   Test timestamps, actual and forecast demand
  outputs/forecast_chart.png     Actual vs forecast, final test week
  outputs/mock_prediction.json   Example local-data prediction
  docs/member2_report.md         Text ready to adapt into the team PDF report
  requirements.txt               Libraries
  README.md                      This file
```

## Reproduce from scratch

**Repository layout required:** place this folder directly inside `energyConsumption/`, alongside the shared root-level `pjme_clean.csv`. Do not commit another duplicate CSV in the member folder.

Use Python 3.10+ with pip installed. From the `member2_forecasting` folder:

```bash
python -m pip install -r requirements.txt
python scripts/train.py
python scripts/predict.py --mock
python -m unittest discover -s tests -v
```

The training script reads the **shared cleaned dataset in the parent repository folder** and regenerates all model outputs, including the plot. It may take some time depending on the computer.

## Model and validation design

The shared `pjme_clean.csv` has **145,392 rows**, no duplicate timestamps and a continuous hourly grid. It includes `Datetime`, `PJME_MW`, `was_imputed` and `temperature_c`. The 30 records with `was_imputed=True` were estimated using interpolation and **are excluded from model training inputs and targets** to prevent future-data leakage. Rows requiring those readings in the prior 168 hours are also excluded, leaving **140,154 supervised rows**. The `temperature_c` column is retained in the dataset for team analysis but is not a model predictor until its original source and prediction-time availability are established.

Each labeled row for timestamp `t` uses only observations before `t`:

- Calendar features: `hour`, `day_of_week`, `month`, `day_of_year`, `is_weekend`.
- Lag features: `lag_1`, `lag_24`, `lag_168` (observations at t−1, t−24, t−168).
- Rolling means: `rolling_mean_24`, `rolling_mean_168` of the **preceding** 24 and 168 readings (the target hour is excluded).

After chronological sorting and filtering, first **70%** of usable rows are training, next **15%** validation and last **15%** test. We compare three parameter configurations of `HistGradientBoostingRegressor`, select the lowest validation RMSE, refit on train plus validation, and evaluate the untouched test interval. A naive predictor using the previous hour provides a baseline, with 24-hour and 168-hour seasonal baselines included for context.

| Model | Validation RMSE (MW) |
|---|---:|
| Experiment 1: 100 iterations, 15 leaves, learning rate 0.10, L2 0 | 542.559 |
| **Experiment 2: 180 iterations, 31 leaves, learning rate 0.07, L2 1 (selected)** | **445.934** |
| Experiment 3: 240 iterations, 15 leaves, learning rate 0.05, L2 5 | 518.941 |

Final held-out test results for the selected model: **MAE 337.456 MW, RMSE 447.727 MW, R² 0.99524**. The naive previous-hour baseline has **MAE 1,060.467 MW** on the same interval.

**Evaluation interpretation:** These metrics are from repeated **one-hour-ahead** forecasts, each using *actually observed* previous demand readings. They are **not** a simulation of predicting many future hours without intervening observed readings, and are **not** claimed to show performance on new 2026 data.

## Integration contract for Member 4

Provide an HTTP **GET** route that returns the **most recent 168 consecutive hourly observations**, preferably 200 for a buffer. Each object must use the **exact case-sensitive** keys `Datetime` and `PJME_MW`. Include `was_imputed` (boolean) where possible to ensure interpolated records are rejected for forecasting:

```json
{
  "records": [
    { "Datetime": "2018-08-02T21:00:00", "PJME_MW": 33800.0, "was_imputed": false },
    { "Datetime": "2018-08-02T22:00:00", "PJME_MW": 34125.0, "was_imputed": false }
  ]
}
```

The short example shows the JSON **shape only**; it does not contain enough history to forecast. The `was_imputed` field matters: when it is `true`, the model refuses to use that estimated demand value as if it had been observed. Member 4 should expose this flag. A plain JSON array is also accepted. Records may be ordered or unordered. The script sorts timestamps and validates that the latest 168 hours have no gaps. All timestamps should use the same **naive local time convention** as the original dataset. Agree on a consistent convention with the group before deploying.

After Member 4 shares their real address, for example:

```bash
python scripts/predict.py --api-url "http://localhost:8000/sql/records/recent?limit=200"
```

This is an **illustrative URL**, not a confirmed route. The real URL depends on how Member 4 implements the API. If the API returns different JSON names, update the team contract consistently; do not silently rename columns during evaluation.

Expected JSON output has `forecast_for`, `predicted_PJME_MW` and `source` fields. In mock mode, the historical last timestamp is `2018-08-03 00:00:00` and the demonstration forecast is **32,450.41 MW for 2018-08-03 01:00:00**.

## Tests

```bash
python -m unittest discover -s tests -v
```

This checks:

1. Training and next-hour prediction construct mathematically identical feature values.
2. Reverse-ordered API results remain usable.
3. Insufficient or interrupted history is rejected instead of silently forecasting.
4. The group's imputation flags are respected.
5. A local HTTP server returns JSON that the prediction client fetches and successfully uses.

## Limitations relevant to marking

- The **shared cleaned CSV** includes `PJME_MW` and `temperature_c`. **Ask the group member who added temperature to document its source, station/region, collection process and timestamp alignment.** Do not label it observed weather data or use it for forecasting until its provenance and prediction-time availability are confirmed. The model itself currently uses demand history and calendar variables.
- Daylight-saving gaps remain ambiguous because timestamps have no explicit timezone. Although the shared CSV fills 30 missing hours by interpolation, the model masks those estimated values during training and prediction feature construction. Predictions immediately after those gaps may be rejected until 168 fully observed hours are available.
- The model is a strong **historical one-step** benchmark, not evidence of multi-step or future-year forecasting quality.
- The script expects the group-level `pjme_clean.csv` immediately above the `member2_forecasting` folder. The scripts cover Member 2 work only. Member 3 handles the actual databases; Member 4 must provide the real API and demonstrate the final end-to-end route.
- The class rubric asks for **at least four meaningful commits per student**. Students must genuinely review, reproduce, adapt and document their own contribution. A packaged project file is not itself evidence of independent authorship or commits.
