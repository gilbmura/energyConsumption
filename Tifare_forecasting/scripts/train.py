"""Reproducible one-hour-ahead PJME forecasting with a held-out test set.

Run: python scripts/train.py

Data policy:
- Target timestamp t is predicted from readings strictly older than t.
- Chronological 70/15/15 split (after row filtering).
- Only validation metrics select hyperparameters; test is reserved for the end.
- This evaluates rolling one-step forecasting with *observed* historical lags.
"""
from pathlib import Path
import json

import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from features import FEATURES, make_feature_frame, to_hourly_series

ROOT = Path(__file__).resolve().parents[1]
TRIALS = [
    ('Experiment 1', {'max_iter': 100, 'max_leaf_nodes': 15, 'learning_rate': 0.10, 'l2_regularization': 0.0}),
    ('Experiment 2', {'max_iter': 180, 'max_leaf_nodes': 31, 'learning_rate': 0.07, 'l2_regularization': 1.0}),
    ('Experiment 3', {'max_iter': 240, 'max_leaf_nodes': 15, 'learning_rate': 0.05, 'l2_regularization': 5.0}),
]


def metrics(actual, predicted) -> dict:
    return {
        'MAE': round(float(mean_absolute_error(actual, predicted)), 3),
        'RMSE': round(float(np.sqrt(mean_squared_error(actual, predicted))), 3),
        'R2': round(float(r2_score(actual, predicted)), 5),
    }


def main():
    source = ROOT.parent / 'pjme_clean.csv'
    if not source.is_file():
        raise FileNotFoundError(f'Expected the shared group dataset at {source}')
    raw = pd.read_csv(source)
    hourly = to_hourly_series(raw)
    frame = make_feature_frame(hourly)
    df = frame.dropna(subset=['target'] + FEATURES)

    n = len(df)
    train_end, validation_end = int(n * .70), int(n * .85)
    training = df.iloc[:train_end]
    validation = df.iloc[train_end:validation_end]
    train_and_validation = df.iloc[:validation_end]
    testing = df.iloc[validation_end:]

    experiments = []
    for name, params in TRIALS:
        model = HistGradientBoostingRegressor(random_state=42, **params)
        model.fit(training[FEATURES], training['target'])
        score = metrics(validation['target'], model.predict(validation[FEATURES]))
        experiments.append({
            'experiment': name, **params, **{f'validation_{key}': val for key, val in score.items()},
        })
        print(f'{name}: validation RMSE = {score["RMSE"]:,.2f} MW')

    winner = min(experiments, key=lambda row: row['validation_RMSE'])
    winning_params = next(params for name, params in TRIALS if name == winner['experiment'])
    model = HistGradientBoostingRegressor(random_state=42, **winning_params)
    model.fit(train_and_validation[FEATURES], train_and_validation['target'])
    predicted = model.predict(testing[FEATURES])

    output = ROOT / 'outputs'
    output.mkdir(exist_ok=True)
    (ROOT / 'models').mkdir(exist_ok=True)
    joblib.dump({
        'model': model,
        'features': FEATURES,
        'target': 'PJME_MW',
        'frequency': 'hourly',
        'forecast_horizon_hours': 1,
    }, ROOT / 'models' / 'pjme_forecast.joblib')

    pd.DataFrame(experiments).to_csv(output / 'experiments.csv', index=False)
    pd.DataFrame({
        'Datetime': testing.index,
        'actual_MW': testing['target'].values,
        'predicted_MW': predicted,
    }).to_csv(output / 'test_predictions.csv', index=False)

    # An independently reproducible plot: the final week of the test interval.
    recent = pd.DataFrame({'Actual': testing['target'], 'Forecast': predicted}, index=testing.index).tail(24 * 7)
    fig, ax = plt.subplots(figsize=(11, 4.5))
    recent.plot(ax=ax, linewidth=1.4)
    ax.set(title='PJME one-hour-ahead forecast: final test week', xlabel='Timestamp', ylabel='Demand (MW)')
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(output / 'forecast_chart.png', dpi=165)
    plt.close(fig)

    report = {
        'raw_rows': len(raw),
        'duplicate_timestamps': int(pd.to_datetime(raw['Datetime']).duplicated().sum()),
        'imputed_records_excluded': int(raw['was_imputed'].astype(str).str.lower().eq('true').sum()),
        'missing_hourly_timestamps': len(hourly) - len(raw['Datetime'].unique()),
        'unobserved_hours_including_imputed': int(hourly.isna().sum()),
        'hourly_grid_rows': len(hourly),
        'model_rows': n,
        'first_raw_timestamp': str(hourly.index.min()),
        'last_raw_timestamp': str(hourly.index.max()),
        'start': str(df.index.min()),
        'end': str(df.index.max()),
        'train_rows': len(training),
        'validation_rows': len(validation),
        'test_rows': len(testing),
        'train_end': str(training.index.max()),
        'validation_end': str(validation.index.max()),
        'test_start': str(testing.index.min()),
        'best_experiment': winner['experiment'],
        'best_parameters': winning_params,
        'test_metrics': metrics(testing['target'], predicted),
        'naive_lag1_test_metrics': metrics(testing['target'], testing['lag_1']),
        'naive_lag24_test_metrics': metrics(testing['target'], testing['lag_24']),
        'naive_lag168_test_metrics': metrics(testing['target'], testing['lag_168']),
        'features': FEATURES,
        'notes': (
            'One-step-ahead with observed earlier-hour values, not multi-step recursive prediction. '
            'Training uses shared pjme_clean.csv. Interpolated values marked was_imputed are masked '
            'to avoid information from future hours. Incomplete lag-history rows are excluded. '
            'Validation used for parameter selection and held-out test only for final evaluation.'
        ),
    }
    (output / 'metrics.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
