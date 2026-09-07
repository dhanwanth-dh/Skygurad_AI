"""Station baseline features — per-station rolling median/std and deviation scores.

Baselines are computed from training data only and applied to all splits.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

SENSOR_COLS = [
    "temperature_c",
    "relative_humidity_pct",
    "pressure_hpa",
    "wind_speed_kmh",
    "rainfall_mm",
]


def compute_station_baselines(
    train_df: pd.DataFrame,
    sensor_cols: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Compute per-station, per-hour median and MAD from training data.

    Returns a nested dict: baselines[station_id][col] = {hour -> (median, mad)}
    """
    cols = sensor_cols or SENSOR_COLS
    baselines: dict[str, dict[str, Any]] = {}

    for station, grp in train_df.groupby("station_id"):
        baselines[station] = {}
        for col in cols:
            src = f"{col}_clean" if f"{col}_clean" in grp.columns else col
            if src not in grp.columns:
                continue
            hour_stats: dict[int, tuple[float, float]] = {}
            for hour, hgrp in grp.groupby(grp["timestamp"].dt.hour):
                vals = hgrp[src].dropna()
                if len(vals) == 0:
                    continue
                med = float(vals.median())
                mad = float((vals - med).abs().median())
                hour_stats[int(hour)] = (med, max(mad, 1e-6))
            baselines[station][col] = hour_stats

    return baselines


def apply_station_baselines(
    df: pd.DataFrame,
    baselines: dict[str, dict[str, Any]],
    sensor_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Add baseline and deviation columns using pre-computed baselines.

    Features added per sensor column:
    - <col>_baseline   : expected value from training hour-of-day median
    - <col>_deviation  : observed - baseline
    - <col>_robust_z   : deviation / MAD (robust z-score)
    """
    df = df.copy()
    cols = sensor_cols or SENSOR_COLS

    for col in cols:
        df[f"{col}_baseline"] = np.nan
        df[f"{col}_deviation"] = np.nan
        df[f"{col}_robust_z"] = np.nan

    for station, grp_idx in df.groupby("station_id").groups.items():
        grp = df.loc[grp_idx]
        if station not in baselines:
            logger.warning("No baseline for station %s", station)
            continue

        for col in cols:
            src = f"{col}_clean" if f"{col}_clean" in df.columns else col
            if src not in df.columns or col not in baselines[station]:
                continue

            hour_stats = baselines[station][col]
            hours = grp["timestamp"].dt.hour

            medians = hours.map(lambda h: hour_stats.get(h, (np.nan, np.nan))[0])
            mads = hours.map(lambda h: hour_stats.get(h, (np.nan, np.nan))[1])

            df.loc[grp_idx, f"{col}_baseline"] = medians.values
            df.loc[grp_idx, f"{col}_deviation"] = (grp[src].values - medians.values)
            df.loc[grp_idx, f"{col}_robust_z"] = (
                (grp[src].values - medians.values) / mads.replace(0, np.nan).values
            )

    return df
