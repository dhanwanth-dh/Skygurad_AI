"""Spatial feature engineering — Haversine distances and neighbor aggregation.

Only uses observations at the same timestamp as the target observation.
No forward-filling of future neighbor data.
"""

from __future__ import annotations

import logging

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


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    R = 6371.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
    return float(R * 2 * np.arcsin(np.sqrt(a)))


def build_station_coords(df: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """Extract unique station coordinates."""
    return {
        row["station_id"]: (float(row["latitude"]), float(row["longitude"]))
        for _, row in df.drop_duplicates("station_id").iterrows()
    }


def add_spatial_features(
    df: pd.DataFrame,
    sensor_cols: list[str] | None = None,
    k_neighbors: int = 2,
) -> pd.DataFrame:
    """Add neighbor-based spatial features (vectorized for high performance).

    For each observation, finds the k nearest stations that have an observation
    at the same timestamp and computes:
    - neighbor_<col>_mean / _std
    - spatial_<col>_residual  (observed - neighbor mean)
    - neighbor_agreement_score (mean absolute spatial residual, normalized)
    - nearest_station_distance_km
    """
    df = df.copy()
    cols = sensor_cols or SENSOR_COLS
    coords = build_station_coords(df)
    stations = list(coords.keys())

    if len(stations) <= 1:
        for col in cols:
            df[f"neighbor_{col}_mean"] = np.nan
            df[f"neighbor_{col}_std"] = np.nan
            df[f"spatial_{col}_residual"] = np.nan
        df["nearest_station_distance_km"] = np.nan
        df["neighbor_agreement_score"] = np.nan
        return df

    # Pre-compute pairwise distances & k-nearest stations
    dist_matrix: dict[str, dict[str, float]] = {}
    for s1 in stations:
        dist_matrix[s1] = {}
        for s2 in stations:
            if s1 == s2:
                dist_matrix[s1][s2] = float("inf")
            else:
                dist_matrix[s1][s2] = haversine_km(*coords[s1], *coords[s2])

    nearest_k = {s: sorted(dist_matrix[s].keys(), key=lambda x: dist_matrix[s][x])[:k_neighbors] for s in stations}
    nearest_dist = {s: dist_matrix[s][nearest_k[s][0]] for s in stations}

    df["nearest_station_distance_km"] = df["station_id"].map(nearest_dist)

    # Initialize columns
    for col in cols:
        df[f"neighbor_{col}_mean"] = np.nan
        df[f"neighbor_{col}_std"] = np.nan
        df[f"spatial_{col}_residual"] = np.nan

    # Fast Vectorized Computation using Pivot Table
    indexed_df = df.set_index(["timestamp", "station_id"])
    for col in cols:
        src = f"{col}_clean" if f"{col}_clean" in df.columns else col
        if src not in df.columns:
            continue
        piv = df.pivot_table(index="timestamp", columns="station_id", values=src, aggfunc="first")

        n_mean_dict = {}
        n_std_dict = {}
        for s in stations:
            n_ids = [n for n in nearest_k.get(s, []) if n in piv.columns]
            if n_ids:
                n_mean_dict[s] = piv[n_ids].mean(axis=1)
                n_std_dict[s] = piv[n_ids].std(axis=1).fillna(0.0)
            else:
                n_mean_dict[s] = pd.Series(np.nan, index=piv.index)
                n_std_dict[s] = pd.Series(np.nan, index=piv.index)

        n_mean_df = pd.DataFrame(n_mean_dict, index=piv.index)
        n_std_df = pd.DataFrame(n_std_dict, index=piv.index)
        n_mean_df.columns.name = "station_id"
        n_std_df.columns.name = "station_id"

        mean_s = n_mean_df.stack(future_stack=True)
        std_s = n_std_df.stack(future_stack=True)

        indexed_df[f"neighbor_{col}_mean"] = mean_s
        indexed_df[f"neighbor_{col}_std"] = std_s
        indexed_df[f"spatial_{col}_residual"] = indexed_df[src] - indexed_df[f"neighbor_{col}_mean"]

    df = indexed_df.reset_index()

    res_cols = [f"spatial_{c}_residual" for c in cols if f"spatial_{c}_residual" in df.columns]
    if res_cols:
        df["neighbor_agreement_score"] = df[res_cols].abs().mean(axis=1)
    else:
        df["neighbor_agreement_score"] = np.nan

    return df
