"""Preprocessing cleaner — imputes missing values using forward-fill per station.

Raw values are preserved; imputed values go into separate columns.
"""

from __future__ import annotations

import pandas as pd

SENSOR_COLS = [
    "temperature_c",
    "relative_humidity_pct",
    "pressure_hpa",
    "wind_speed_kmh",
    "rainfall_mm",
]


def impute_per_station(df: pd.DataFrame, sensor_cols: list[str] | None = None) -> pd.DataFrame:
    """Forward-fill then backward-fill missing sensor values per station.

    Creates <col>_clean columns; never overwrites raw columns.
    """
    df = df.copy()
    cols = sensor_cols or SENSOR_COLS

    df = df.sort_values(["station_id", "timestamp"])

    for col in cols:
        if col not in df.columns:
            continue
        clean_col = f"{col}_clean"
        df[clean_col] = df.groupby("station_id")[col].transform(
            lambda s: s.ffill().bfill().fillna(0.0 if col == "rainfall_mm" else s.median())
        )
        # Ensure no remaining NaNs
        if df[clean_col].isna().any():
            df[clean_col] = df[clean_col].fillna(0.0 if col == "rainfall_mm" else df[clean_col].median())

    return df


def clip_physical(df: pd.DataFrame, bounds: dict[str, tuple[float, float]]) -> pd.DataFrame:
    """Clip _clean columns to physical bounds for downstream feature engineering.

    Does NOT clip raw columns.
    """
    df = df.copy()
    for col, (lo, hi) in bounds.items():
        clean_col = f"{col}_clean"
        if clean_col in df.columns:
            df[clean_col] = df[clean_col].clip(lo, hi)
    return df
