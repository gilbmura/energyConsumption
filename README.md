# PJME Energy Consumption Pipeline

## Project Overview

This project was developed for the Working with Time Series Data group assignment. We built an end-to-end pipeline to analyze historical electricity consumption, store observations in relational and non-relational databases, expose them through API endpoints, and predict electricity demand one hour ahead.

The prediction target is `PJME_MW`, hourly electricity demand in megawatts for the PJM East region. Our cleaned dataset contains 145,392 hourly records from 1 January 2002 to 3 August 2018.

## Team and Contributions

| Member | Main responsibility |
| --- | --- |
| David NGARAMBE | Dataset preprocessing, exploratory analysis and analytical questions (Tasks 1A and 1B) |
| Tifare Kaseke | Machine learning, hyperparameter tuning and forecasting integration (Tasks 1C and 4) |
| Laura Karangwa | MySQL and MongoDB database design and queries (Task 2) |
| Gilbert Muramirabagabo | API development, CRUD endpoints and integration tests (Task 3) |

All four components form one integrated project, and final integration was tested together.

## Dataset and Sources

| File | Source | Description |
| --- | --- | --- |
| `data/raw/PJME_hourly.csv` | [Kaggle: Hourly Energy Consumption](https://www.kaggle.com/datasets/robikscube/hourly-energy-consumption) | Original hourly PJM East electricity demand |
| `data/raw/philadelphia_temperature.csv` | [Open-Meteo Historical Archive](https://open-meteo.com/) | Philadelphia hourly air temperature in degrees Celsius |
| `data/processed/pjme_clean.csv` | EDA preprocessing notebook | Cleaned hourly demand and temperature observations |
| `data/processed/pjme_features.csv` | EDA feature engineering | Exploratory model-ready features |
| `pjme_clean.csv` | Shared project dataset | Authoritative CSV used by the database loader and forecasting pipeline |

The source Kaggle dataset contains one original measured variable, electricity demand. We added Philadelphia hourly temperature as an external measured variable to study relationships between weather and electricity usage. One city is used as an approximation for the larger PJM East region.

The historical temperature download was configured using Open-Meteo's archive endpoint:

```text
https://archive-api.open-meteo.com/v1/archive?latitude=39.95&longitude=-75.16&start_date=2002-01-01&end_date=2018-08-03&hourly=temperature_2m&timezone=America%2FNew_York&format=csv
```

The electricity timestamps are stored without explicit timezone offsets. Our data processing and database APIs preserve these clock labels rather than converting them. The team should verify the original source timezone and daylight-saving alignment before treating the weather-to-demand match as fully established.

### Shared Columns

| Column | Meaning |
| --- | --- |
| `Datetime` | Hourly timestamp |
| `PJME_MW` | Hourly electricity consumption, our forecasting target |
| `temperature_c` | Hourly air temperature in degrees Celsius |
| `was_imputed` | Whether demand was filled during cleaning |
| `hour` | Hour of day |
| `day_of_week` | Weekday, where Monday = 0 |
| `month` | Month of year |
| `day_of_year` | Day number within the year |
| `is_weekend` | Weekend indicator |
| `lag_1`, `lag_24`, `lag_168` | Demand 1, 24 and 168 hours earlier |
| `rolling_mean_24`, `rolling_mean_168` | Means of prior demand over 24 and 168 hours |

Calendar, lag and rolling-average features are derived rather than additional original measured variables. The forecasting pipeline computes them during training and prediction rather than storing potentially stale lag features in the databases.

## Repository Structure

```text
energyConsumption/
├── data/
│   ├── raw/
│   └── processed/
├── notebooks/
│   ├── 01_eda_preprocessing.ipynb
│   ├── 02_analytical_questions_part1.ipynb
│   └── 03_analytical_questions_part2.ipynb
├── reports/
│   └── figures/
├── databases/
├── api/
├── Tifare_forecasting/
├── pjme_clean.csv
├── requirements.txt
└── README.md
```

The root `pjme_clean.csv` is the shared input used by the integrated loader and prediction pipeline. The files under `data/` document David's data preparation workflow.

### Dataset handoff

The two cleaned CSV files serve different stages of the current workflow:

- `data/processed/pjme_clean.csv` is the output of `notebooks/01_eda_preprocessing.ipynb` and the input to the later analytical notebooks.
- The root `pjme_clean.csv` is the shared input read by the database loader, forecasting scripts and related tests.

Rerunning preprocessing updates only the copy under `data/processed/`. It does not automatically refresh the root copy, either database, or the saved forecasting model.

After the team reviews and accepts a preprocessing change:

1. Keep the four shared columns: `Datetime`, `PJME_MW`, `was_imputed` and `temperature_c`.
2. From the repository root, synchronize the accepted output to the shared input:

   ```powershell
   Copy-Item -LiteralPath data/processed/pjme_clean.csv -Destination pjme_clean.csv
   ```

   This replaces the root copy. Run it only when the processed file is the version the team intends to use.
3. Validate the shared input before reloading databases or retraining:

   ```powershell
   & api/.venv/Scripts/python.exe -m databases.scripts.load_csv_to_databases --validate-only
   ```

4. Reload the databases and rerun training and verification when the accepted data change requires updated results. Commit both CSV copies together when their contents change, so other members receive the same observations.

Keep both files while the existing notebooks and application scripts use these separate paths. The feature table `data/processed/pjme_features.csv` is a separate exploratory output and must not replace either cleaned CSV.

## Task 1A: Data Exploration and Preprocessing

We inspected the raw demand file and found:

- 145,366 original hourly readings.
- Four duplicate timestamps.
- Thirty missing hourly positions when aligned to a continuous hourly index.
- Records that were not in chronological order.

We sorted the records, averaged duplicate timestamps and filled missing hourly positions using time-based linear interpolation. The 30 interpolated rows are marked using `was_imputed`. The cleaned dataset contains 145,392 hourly records.

We retained extreme electricity demand observations because real peaks are important for understanding electricity demand and evaluating forecasting models.

For forecasting, interpolated demand values were masked to prevent information from future observations leaking into historical features. We also excluded rows without sufficient valid lag history.

### Run the EDA Notebooks

Install the required Python dependencies and open the notebooks:

```powershell
python -m pip install -r requirements.txt
cd notebooks
jupyter notebook
```

Run the notebooks in order:

1. `01_eda_preprocessing.ipynb`
2. `02_analytical_questions_part1.ipynb`
3. `03_analytical_questions_part2.ipynb`

The notebooks use relative paths, so launch Jupyter from inside the `notebooks` folder.

## Task 1B: Analytical Questions

We investigated six analytical questions:

| Question | Main finding |
| --- | --- |
| Q1: Is there a long-term demand trend? | The estimated annual trend is approximately -84 MW per year, with p = 0.054. |
| Q2: How does demand change during the day and week? | Demand peaks in the evening on weekdays; average weekend consumption is 9.7% lower. |
| Q3: How does consumption change across seasons? | Demand peaks in July, has a secondary peak in January and is lowest in April. |
| Q4: How does temperature relate to electricity demand? | The relationship is approximately U-shaped, with lowest average demand near 13°C. |
| Q5: Are there lag effects? | Demand is strongly correlated with demand 1, 24 and 168 hours earlier. |
| Q6: How do moving averages behave? | Rolling averages smooth daily and weekly fluctuations and provide historical context. |

Charts and interpretations are included in the EDA notebooks and `reports/figures/`.

## Task 1C: Machine Learning and Forecasting

We trained a Histogram Gradient Boosting Regressor to predict electricity demand one hour ahead.

The model uses calendar features, historical demand lags and rolling averages. Temperature is not currently a forecasting input because prediction-time temperature availability and timestamp alignment require further confirmation.

### Model Features

```text
hour
day_of_week
month
day_of_year
is_weekend
lag_1
lag_24
lag_168
rolling_mean_24
rolling_mean_168
```

The modeling records were split chronologically into training, validation and test sets to avoid random mixing of historical and future observations.

### Hyperparameter Experiments

| Experiment | Iterations | Leaf nodes | Learning rate | L2 regularization | Validation RMSE |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 100 | 15 | 0.10 | 0 | 535.70 MW |
| 2 (selected) | 180 | 31 | 0.07 | 1 | 444.74 MW |
| 3 | 240 | 15 | 0.05 | 5 | 513.90 MW |

Experiment 2 had the lowest validation RMSE and was selected for the final model.

### Final Test Performance

| Metric | Result |
| --- | ---: |
| Mean Absolute Error (MAE) | 340.86 MW |
| Root Mean Squared Error (RMSE) | 451.68 MW |
| R² | 0.99516 |

The model was compared against naive forecasts based on previous-hour, previous-day and previous-week demand. The saved forecasting model and scripts are in `Tifare_forecasting/`.

## Task 2: MySQL and MongoDB Databases

We implemented both a relational and a non-relational database using the shared cleaned dataset.

### MySQL

The MySQL database contains three related tables:

- `data_sources`
- `time_dimensions`
- `energy_readings`

The schema uses primary keys, foreign keys, validation constraints and indexes.

### MongoDB

The MongoDB database uses the `energy_observations` collection with observations, calendar information and temperature stored in documents.

We implemented queries for hourly demand statistics, date ranges, temperature groups and other analysis. SQL schema, MongoDB setup, example documents and query scripts are located in `databases/`.

The actual live query results can be generated using:

```powershell
& api/.venv/Scripts/python.exe -m databases.scripts.execute_queries_and_export_results
```

Results are saved in `databases/results/live_query_results.json`.

## Task 3: FastAPI CRUD and Time-Series Endpoints

We created a FastAPI backend for both MySQL and MongoDB.

Both backends provide:

| Method | Endpoint | Function |
| --- | --- | --- |
| POST | `/{backend}/records` | Create an observation |
| GET | `/{backend}/records` | List observations |
| GET | `/{backend}/records/{id}` | Retrieve an observation |
| PUT | `/{backend}/records/{id}` | Update an observation |
| DELETE | `/{backend}/records/{id}` | Delete an observation |
| GET | `/{backend}/records/latest` | Retrieve latest observation |
| GET | `/{backend}/records/range` | Retrieve observations by date range |
| GET | `/{backend}/records/recent` | Retrieve recent historical records |

Replace `{backend}` with `mysql` or `mongo`.

Swagger UI is available at `http://127.0.0.1:8000/docs` when the application is running.

## Environment Setup

From the project root on Windows PowerShell:

```powershell
python -m venv api/.venv
python -m pip --python api/.venv/Scripts/python.exe install -r requirements.txt
```

The saved forecasting model uses scikit-learn 1.9.1, which is pinned in the requirements. The repository also includes `api/requirements-lock.txt` for additional environment reproducibility.

### Start MySQL and MongoDB with Docker

```powershell
docker compose -f api/compose.yaml up -d --wait
docker compose -f api/compose.yaml ps
```

By default, the Docker setup exposes MySQL on port 3307 and MongoDB on port 27018.

Copy the example environment configuration once:

```powershell
Copy-Item api/.env.example api/.env
```

Check and adapt local credentials as needed. Do not commit `api/.env` containing private credentials.

### Validate and Load the Dataset

```powershell
& api/.venv/Scripts/python.exe -m databases.scripts.load_csv_to_databases --validate-only
& api/.venv/Scripts/python.exe -m databases.scripts.load_csv_to_databases
```

The loader validates the source dataset and upserts observations into each database. The two database operations commit independently.

### Start the API

```powershell
& api/.venv/Scripts/python.exe -m uvicorn api.app.main:app --host 127.0.0.1 --port 8000
```

Leave the API terminal running while testing endpoints.

## Task 4: Forecasting API Integration

The forecasting script retrieves recent historical observations through an API, validates the input, creates the same features used during model training, loads the saved model and predicts electricity demand for the next hour.

It requires at least 168 consecutive, valid historical hourly observations.

With the API running, use these commands in a second PowerShell terminal:

### Forecast from MySQL

```powershell
& api/.venv/Scripts/python.exe -m Tifare_forecasting.scripts.predict --api-url "http://127.0.0.1:8000/mysql/records/recent?limit=200"
```

### Forecast from MongoDB

```powershell
& api/.venv/Scripts/python.exe -m Tifare_forecasting.scripts.predict --api-url "http://127.0.0.1:8000/mongo/records/recent?limit=200"
```

Both database APIs produced the same historical demonstration forecast:

```json
{
  "forecast_for": "2018-08-03 01:00:00",
  "predicted_PJME_MW": 32562.82
}
```

The matching forecasts verify consistent input handling through both database backends. The test-set metrics provide separate evidence of forecasting accuracy.

## Testing and Verification

The combined integration suite was run with MySQL and MongoDB in Docker, the FastAPI service and the saved forecasting model.

### Verified Results

- MySQL records loaded: 145,392.
- MongoDB records loaded: 145,392.
- Matching API forecasts: 32,562.82 MW.
- Automated tests passed: 150.
- Failed tests: 0.
- Deprecation warnings: 10.

Run the complete live-database test suite:

```powershell
& api/.venv/Scripts/python.exe -m pytest -c api/pytest.ini api/tests Tifare_forecasting/tests --live-databases -q --junitxml=api/evidence/integration-live-tests.xml
```

This creates a JUnit XML test report. Additional dataset, API and forecast evidence is stored under `api/evidence/`.

The test environment uses local databases for educational verification; it is not a production deployment. The forecasting results demonstrate one-hour-ahead prediction on historical data, not future real-world performance.

## Limitations and Future Improvements

- Philadelphia temperature approximates weather conditions across the wider PJM East region.
- The original demand timestamp timezone and daylight-saving alignment should be documented carefully.
- Thirty electricity demand observations were interpolated and flagged.
- Forecasting uses historical demand and calendar features, not forecasted weather.
- The model was evaluated on historical holdout data, so accuracy on newer electricity demand patterns is not established.
- This coursework API is a local implementation and does not include production authentication and authorization.

## Additional Documentation

- [Database documentation](databases/README.md)
- [API documentation](api/README.md)
- [API integration guide](api/INTEGRATION.md)
- [Forecasting documentation](Tifare_forecasting/README.md)

## Final Submission

The group submission includes a PDF report and the GitHub repository link. The report presents the exploratory analysis, machine learning experiments, database schemas and query results, API endpoints, complete prediction pipeline, and contributions of each group member.
