"""Temporal feature engineering — lags, deltas, rolling stats, time encodings.

All features are computed per station using only past observations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SENSOR_COLS = [
    "temperature_c",
    "relative_humidity_pct",
    "pressure_hpa",
    "wind_speed_kmh",
    "rainfall_mm",
]


def add_temporal_features(
    df: pd.DataFrame,
    lag_steps: list[int] | None = None,
    rolling_windows: list[int] | None = None,
    sensor_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Add lag, delta, rolling, and time-encoding features per station.

    Uses _clean columns as source to avoid NaN propagation.
    All shifts/rolling operations are strictly backward-looking.
    """
    df = df.copy().sort_values(["station_id", "timestamp"])
    lags = lag_steps or [1, 2, 3]
    windows = rolling_windows or [3, 6]
    cols = sensor_cols or SENSOR_COLS

    for col in cols:
        src = f"{col}_clean" if f"{col}_clean" in df.columns else col
        if src not in df.columns:
            continue

        grp = df.groupby("station_id")[src]

        # Lag features
        for lag in lags:
            df[f"{col}_lag{lag}"] = grp.shift(lag)

        # Delta (first difference)
        df[f"{col}_delta"] = grp.shift(0) - grp.shift(1)

        # Rolling statistics (min_periods=2 to avoid NaN on first row)
        for w in windows:
            rolled = grp.shift(1).rolling(window=w, min_periods=2)
            df[f"{col}_roll{w}_mean"] = rolled.mean().reset_index(level=0, drop=True)
            df[f"{col}_roll{w}_std"] = rolled.std().reset_index(level=0, drop=True)

        # Rolling z-score using the largest window
        w_max = max(windows)
        mean_col = f"{col}_roll{w_max}_mean"
        std_col = f"{col}_roll{w_max}_std"
        if mean_col in df.columns and std_col in df.columns:
            df[f"{col}_roll_zscore"] = (
                (df[src] - df[mean_col]) / (df[std_col].replace(0, np.nan))
            )

    # Time since previous observation per station (hours)
    df["time_since_prev_obs"] = (
        df.groupby("station_id")["timestamp"]
        .diff()
        .dt.total_seconds()
        .div(3600)
    )

    # Calendar encodings
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["day_of_year"] = df["timestamp"].dt.dayofyear
    df["month"] = df["timestamp"].dt.month

    return df
