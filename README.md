# Time Series Pipeline: PJM East Electricity Demand

Group assignment *Working with Time Series Data*. The project forecasts hourly electricity demand (`PJME_MW`) for the PJM East region from historical readings, calendar information and temperature.

> This README covers **David's part (Tasks 1A and 1B)**: data understanding, preprocessing, feature engineering and exploratory analysis. Teammates add their own sections for modelling, databases, API and the prediction script.

## Team

| Member | Responsibility |
| --- | --- |
| David NGARAMBE | Exploratory analysis and preprocessing (Tasks 1A, 1B) |
| Tifare Kaseke | Modelling and forecasting script (Tasks 1C, 4) |
| Laura Karangwa | MySQL and MongoDB (Task 2) |
| Gilbert Muramirabagabo | API endpoints (Task 3) |

## Data

| File | Source | Content |
| --- | --- | --- |
| `data/raw/PJME_hourly.csv` | [Kaggle: Hourly Energy Consumption](https://www.kaggle.com/datasets/robikscube/hourly-energy-consumption) | `Datetime`, `PJME_MW` (demand in MW), 2002-01-01 to 2018-08-03 |
| `data/raw/philadelphia_temperature.csv` | [Open-Meteo historical archive](https://open-meteo.com) | Hourly air temperature (°C) at 39.96 N, 75.17 W, Eastern time |
| `data/processed/pjme_clean.csv` | produced by notebook 01 | One row per hour, no missing values: `Datetime`, `PJME_MW`, `was_imputed`, `temperature_c` |
| `data/processed/pjme_features.csv` | produced by notebook 02 | Model-ready table with the shared features below |

The Kaggle file has one measured variable, so hourly temperature was added as a second measured variable (temperature is the main external driver of electricity demand).

### Shared columns

| Column | Meaning |
| --- | --- |
| `Datetime` | Hourly timestamp (local Eastern time) |
| `PJME_MW` | Demand in megawatts, the forecasting target |
| `temperature_c` | Air temperature in °C |
| `hour`, `day_of_week`, `month`, `is_weekend` | Calendar features (`day_of_week`: 0 = Monday) |
| `lag_1`, `lag_24`, `lag_168` | Demand 1 hour, 1 day and 1 week earlier |
| `rolling_mean_24`, `rolling_mean_168` | Mean of the previous 24 / 168 hours, excluding the current hour |
| `was_imputed` | `True` for the 30 hours filled by interpolation |

## Repository structure

```
.
├── data/
│   ├── raw/                 original files, never edited
│   └── processed/           cleaned data and feature table
├── notebooks/
│   ├── 01_eda_preprocessing.ipynb          Task 1A
│   ├── 02_analytical_questions_part1.ipynb Task 1B: features, Q1 to Q3
│   └── 03_analytical_questions_part2.ipynb Task 1B: Q4 to Q6
├── reports/figures/         charts exported for the report
├── requirements.txt
└── README.md
```

## How to reproduce

```bash
pip install -r requirements.txt
cd notebooks
jupyter notebook
```

Run the notebooks **in order** (01, then 02, then 03). Each reads the previous notebook's output from `data/processed/`. The notebooks use relative paths, so start Jupyter from inside `notebooks/`.

To re-download the temperature file, open this link in a browser and save the result as `data/raw/philadelphia_temperature.csv`:

```
https://archive-api.open-meteo.com/v1/archive?latitude=39.95&longitude=-75.16&start_date=2002-01-01&end_date=2018-08-03&hourly=temperature_2m&timezone=America%2FNew_York&format=csv
```

## What Member 1 found

**Data quality (notebook 01).** The raw file is not in time order and has 4 duplicate timestamps and 30 missing hours. 29 of the 30 are daylight-saving effects and one (2010-12-10 00:00) is a genuine gap. The series was rebuilt on a complete hourly index (145,392 rows): duplicates were averaged and missing hours were filled by time-based linear interpolation and flagged in `was_imputed`. Outliers were kept because they are real heat waves and a storm.

**Analytical questions (notebooks 02 and 03).**

| # | Question | Key finding |
| --- | --- | --- |
| Q1 | Long-term trend? | Nearly flat; -84 MW per year, not significant at 5% (p = 0.054) |
| Q2 | Daily and weekly pattern? | Weekday peak at 18:00 to 19:00; weekends are 9.7% lower |
| Q3 | Seasonal pattern? | Peak in July, second peak in January, lowest in April |
| Q4 | Temperature? | U-shaped, minimum near 13 °C; a curve explains 53.9% of variation, a straight line 5.9% |
| Q5 | Lag effects? | Autocorrelation 0.97 (1 h), 0.89 (24 h), 0.78 (168 h); previous-hour forecast has MAE 1,109 MW (3.5%) |
| Q6 | Moving averages? | Smooth the daily and weekly cycles; weaker direct predictors than `lag_1`, useful as context |

**Notes for the modelling task.**

- A trained model must beat a mean absolute error of about 1,109 MW (the previous-hour baseline) to be worth using.
- Temperature acts in a curve, so use a non-linear model or add a feature such as `abs(temperature_c - 13)`.
- If `temperature_c` is an input, it must be available at prediction time (a forecast or a lagged value).
- Split training and test data chronologically, never randomly.
