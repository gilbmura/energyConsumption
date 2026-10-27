"""Shared feature engineering for both training and real-time inference.

All demand features use strictly earlier timestamps. The dataset contains
naive local timestamps, so daylight-saving ambiguity remains a limitation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FEATURES = [
    'hour', 'day_of_week', 'month', 'day_of_year', 'is_weekend',
    'lag_1', 'lag_24', 'lag_168', 'rolling_mean_24', 'rolling_mean_168',
]
HISTORY_HOURS = 168


def to_hourly_series(data: pd.DataFrame) -> pd.Series:
    """Return observed demand on an hourly grid.

    If the group dataset includes `was_imputed`, omit interpolated demand
    values from training history and forecasting inputs to avoid target leakage.
    Missing hours appear as NaN and incomplete supervised rows are excluded.
    """
    required = {'Datetime', 'PJME_MW'}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f'Missing required columns: {sorted(missing)}')
    included = ['Datetime', 'PJME_MW'] + (['was_imputed'] if 'was_imputed' in data.columns else [])
    df = data[included].copy()
    if 'was_imputed' in df.columns:
        flags = df['was_imputed'].astype(str).str.strip().str.lower()
        if not flags.isin(['true', 'false', '1', '0', 'yes', 'no']).all():
            raise ValueError('Invalid was_imputed flag')
        imputed = flags.isin(['true', '1', 'yes'])
        df.loc[imputed, 'PJME_MW'] = float('nan')
    df['Datetime'] = pd.to_datetime(df['Datetime'], errors='raise')
    df['PJME_MW'] = pd.to_numeric(df['PJME_MW'], errors='raise')
    if df.empty or not df['PJME_MW'].notna().any():
        raise ValueError('The input contains no valid electricity observations')
    if df['Datetime'].dt.tz is not None:
        raise ValueError('Expected timezone-naive dataset timestamps; coordinate timezone handling with the database team')
    if df['Datetime'].isna().any() or df['Datetime'].duplicated().any():
        raise ValueError('Timestamps must be present and unique')
    if not df['Datetime'].eq(df['Datetime'].dt.floor('h')).all():
        raise ValueError('Timestamps must be on hourly boundaries')
    observed = df['PJME_MW'].dropna()
    if not np.isfinite(observed).all() or (observed < 0).any():
        raise ValueError('Demand must be finite and nonnegative')
    # Preserve missing/imputed values at BOTH ends so inference never silently
    # shifts backwards to an earlier last-observed hour.
    return df.set_index('Datetime')['PJME_MW'].sort_index().asfreq('h')


def make_feature_frame(series: pd.Series) -> pd.DataFrame:
    """Create supervised features for timestamps on an hourly index.

    For row t, every demand-derived feature uses series[t-1] or earlier.
    Rows with unknown target may be used for *inference*, but not fitting.
    """
    if not isinstance(series.index, pd.DatetimeIndex):
        raise TypeError('Expected a time-indexed pandas Series')
    x = pd.DataFrame(index=series.index)
    x['target'] = series
    x['hour'] = x.index.hour
    x['day_of_week'] = x.index.dayofweek
    x['month'] = x.index.month
    x['day_of_year'] = x.index.dayofyear
    x['is_weekend'] = (x.index.dayofweek >= 5).astype(int)
    for lag in (1, 24, 168):
        x[f'lag_{lag}'] = series.shift(lag)
    for window in (24, 168):
        x[f'rolling_mean_{window}'] = series.shift(1).rolling(window, min_periods=window).mean()
    return x


def make_next_features(records: list[dict]) -> tuple[pd.Timestamp, dict]:
    """Build one next-hour feature row from >=168 consecutive observations.

    Uses exactly the same feature-generation function as training.
    Records may be unordered. Duplicate timestamps are rejected.
    """
    series = to_hourly_series(pd.DataFrame(records))
    if len(series) < HISTORY_HOURS or series.iloc[-HISTORY_HOURS:].isna().any():
        raise ValueError('Need at least 168 consecutive hourly observations ending at the latest timestamp')
    next_time = series.index[-1] + pd.Timedelta(hours=1)
    extended = pd.concat([series.iloc[-HISTORY_HOURS:], pd.Series([float('nan')], index=[next_time])])
    features = make_feature_frame(extended).loc[next_time, FEATURES]
    if features.isna().any():
        raise ValueError('Cannot calculate prediction features from the supplied history')
    return next_time, {key: float(features[key]) for key in FEATURES}
