# Member 2: Machine Learning and Prediction Script

## 1. Problem definition

This component forecasts the **next hour's electricity demand (MW)** in the PJME region using historical demand and timestamp-derived characteristics. Hourly demand forecasts are relevant to short-term electricity planning. The group uses the shared `pjme_clean.csv` derived from Kaggle *Hourly Energy Consumption*. Fields include `Datetime` (timestamp), `PJME_MW` (megawatts), `was_imputed` and `temperature_c`. The original Kaggle CSV provided only demand and time; the team must document the provenance of the additional temperature column.

## 2. Preprocessing and feature engineering

The group cleaned dataset contains **145,392 hourly records, no duplicate timestamps and no absent timestamps**. The original raw dataset had four duplicate timestamps and 30 missing hourly timestamps; the teammate's file already reconciles those issues and marks the 30 estimated demand values `was_imputed=True`. Because each interpolated value uses information from a later timestamp, our forecasting training explicitly masks those 30 estimated demand values. Any supervised row whose target or trailing 168-hour history includes such an estimate is excluded, yielding **140,154 supervised observations**. This avoids inadvertent future-value leakage during historical evaluation.

For a given target timestamp `t`, five calendar predictors are generated directly from `t` (`hour`, `day_of_week`, `month`, `day_of_year`, `is_weekend`). Historical predictors are `lag_1`, `lag_24`, `lag_168`, `rolling_mean_24` and `rolling_mean_168`. Critically, each rolling mean uses observations **strictly before t** by shifting the demand series by one hour before the rolling operation. The current target demand is never used as an input feature. A shared function in `scripts/features.py` is used for both model training and the deployment prediction script, avoiding mismatched feature definitions.

## 3. Training method and hyperparameter experiments

We used a **Histogram Gradient Boosting Regressor**, a nonlinear ensemble model that can learn nonlinear interactions between time indicators and demand lags. The usable chronological observations were split in order into **98,107 training (70%), 21,023 validation (15%) and 21,024 test (15%) rows**, with no random shuffling. The last training timestamp is **2013-09-03 19:00**, the last validation timestamp **2016-02-17 21:00**, and testing begins **2016-02-17 22:00**.

Three settings were tried for `max_iter`, `max_leaf_nodes`, `learning_rate` and `l2_regularization`. Every candidate was fitted to the training portion and evaluated on the validation portion. We selected the lowest validation RMSE, retrained that model on training plus validation data, and evaluated the holdout test set **once after model selection**.

| Experiment | Iterations | Max leaf nodes | Learning rate | L2 regularization | Validation MAE (MW) | Validation RMSE (MW) | Validation R² |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 100 | 15 | 0.10 | 0 | 418.459 | 542.559 | 0.99234 |
| **2, selected** | **180** | **31** | **0.07** | **1** | **337.133** | **445.934** | **0.99483** |
| 3 | 240 | 15 | 0.05 | 5 | 396.951 | 518.941 | 0.99300 |

## 4. Final held-out evaluation

| Predictor | Test MAE (MW) | Test RMSE (MW) | Test R² |
|---|---:|---:|---:|
| **Selected boosting model** | **337.456** | **447.727** | **0.99524** |
| Naive previous-hour demand | 1,060.467 | 1,360.356 | 0.95610 |
| Naive previous-day demand | 2,214.594 | 3,041.527 | 0.78054 |
| Naive previous-week demand | 3,440.273 | 4,748.829 | 0.46502 |

**Interpretation.** On the withheld historical test interval, the selected model's forecast is about **337 MW away from the actual demand on average**, compared with around 1,060 MW for simply repeating the previous hour. The model reproduces short-term demand patterns more accurately than the three simple baselines on this specific interval. The **R² of 0.99524** indicates strong fit on these withheld hours. These values are **not** guarantees of performance for current demand or multi-hour forecasts.

**Figure:** Insert `outputs/forecast_chart.png` into the final PDF and cite it as "Actual versus forecast electricity demand for the final week in the test period". The graph is generated automatically by the training script and shows close tracking, with some deviations near rapid peaks and troughs.

## 5. Prediction script and integration

The training script expects `pjme_clean.csv` at the root of the group repository, immediately above the `member2_forecasting` folder. The trained model, its ordered features, target field and hourly forecast horizon are saved to `models/pjme_forecast.joblib`. `scripts/predict.py` requests JSON through the standard Python HTTP client (`--api-url`) or uses local data to simulate an API (`--mock`). It validates the field names, timestamps and continuous hourly history. To make the **next-hour** forecast, it uses the latest 168 consecutive observed hours to calculate the same features used in model training, loads the saved model, and prints the target timestamp and predicted megawatts as JSON.

**Working local demonstration:** `python scripts/predict.py --mock` outputs **32,450.41 MW** for **2018-08-03 01:00:00**, using historical readings through 2018-08-03 00:00:00.

**HTTP integration verification:** `python -m unittest discover -s tests -v` passes five tests, including a real HTTP GET request and JSON parsing from a local stub server, plus an exact feature-consistency test. An additional test verifies that interpolated readings flagged `was_imputed=True` are excluded. This verifies that the prediction client can consume an HTTP response. **It is not yet a test of Member 4's database-connected API**. When the group API is ready, replace the example URL with the real endpoint, run the client again, save the successful JSON response and add a screenshot/log to the shared PDF report.

## 6. Limitations and responsibilities

1. The shared cleaned file includes demand (`PJME_MW`) and temperature (`temperature_c`). The source, location and time alignment of temperature have not been verified. The forecasting model therefore uses historical demand and calendar features only, not temperature; future temperature must be available at prediction time before it can be a valid predictor.
2. Timezone-naive timestamps involve daylight-saving ambiguities. The shared data is hourly after cleaning, but the model masks estimated missing-hour values and excludes nearby histories rather than using information from later timestamps.
3. Historical test metrics evaluate **rolling one-step-ahead** forecasting with previously observed actual demand. They do not evaluate a multi-step forecast into an unobserved future period.
4. The real API connection remains a group integration step with Member 4.
5. Member 2 should be able to explain the model choice, feature shifts, model selection procedure, evaluation metrics, limitations and the HTTP contract, and record their real GitHub development contributions.
