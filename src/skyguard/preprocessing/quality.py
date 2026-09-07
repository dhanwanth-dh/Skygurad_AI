"""Quality flag layer — adds boolean flag columns without modifying raw values."""

from __future__ import annotations

import numpy as np
import pandas as pd

PHYSICAL_BOUNDS: dict[str, tuple[float, float]] = {
    "temperature_c": (-20.0, 60.0),
    "relative_humidity_pct": (0.0, 100.0),
    "pressure_hpa": (700.0, 1084.0),
    "wind_speed_kmh": (0.0, 200.0),
    "rainfall_mm": (0.0, 500.0),
}


def add_quality_flags(
    df: pd.DataFrame,
    physical_bounds: dict[str, tuple[float, float]] | None = None,
) -> pd.DataFrame:
    """Add quality flag columns to df (in-place copy).

    Flags added:
    - qf_missing_<col>   : True if value is NaN
    - qf_physical_<col>  : True if value is outside physical bounds
    - qf_duplicate_ts    : True if station_id + timestamp is duplicated
    - qf_temporal_gap    : True if gap to previous observation > 1 hour (per station)
    """
    df = df.copy()
    bounds = physical_bounds or PHYSICAL_BOUNDS

    sensor_cols = list(bounds.keys())

    for col in sensor_cols:
        if col in df.columns:
            df[f"qf_missing_{col}"] = df[col].isna()
            lo, hi = bounds[col]
            df[f"qf_physical_{col}"] = (df[col] < lo) | (df[col] > hi)

    df["qf_duplicate_ts"] = df.duplicated(subset=["station_id", "timestamp"], keep=False)

    # Temporal gap flag per station
    df = df.sort_values(["station_id", "timestamp"])
    df["qf_temporal_gap"] = False
    for _, grp in df.groupby("station_id", sort=False):
        expected_freq = pd.Timedelta("1h")
        gaps = grp["timestamp"].diff() > expected_freq
        df.loc[grp.index, "qf_temporal_gap"] = gaps.values

    return df
