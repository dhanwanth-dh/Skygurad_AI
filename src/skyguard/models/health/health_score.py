"""Sensor health score — station-level aggregated health metric (0–100)."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

STATUS_THRESHOLDS = {
    "HEALTHY": 80,
    "NEEDS_ATTENTION": 50,
    "DEGRADED": 20,
    "CRITICAL": 0,
}


def compute_health_scores(
    df: pd.DataFrame,
    weights: dict[str, float] | None = None,
    recent_window_hours: int = 24,
) -> dict[str, dict[str, Any]]:
    """Compute health score per station.

    Formula (weighted sum, each component 0–1, inverted to penalty):
    - fault_rate       : fraction of observations flagged as SENSOR_FAULT
    - anomaly_rate     : fraction with combined_anomaly_score > 0.5
    - missing_rate     : fraction of missing raw sensor values
    - residual_score   : mean absolute temperature residual (normalized)
    - noise_score      : mean rolling std of temperature (normalized)

    health_score = 100 × (1 - weighted_penalty)
    """
    w = weights or {
        "fault_rate": 0.40,
        "anomaly_rate": 0.20,
        "missing_rate": 0.15,
        "residual_score": 0.15,
        "noise_score": 0.10,
    }

    results: dict[str, dict[str, Any]] = {}

    for station, grp in df.groupby("station_id"):
        n = len(grp)
        if n == 0:
            continue

        # Fault rate
        if "ground_truth_label" in grp.columns:
            fault_rate = (grp["ground_truth_label"] == "SENSOR_FAULT").mean()
        else:
            fault_rate = grp.get("rule_any_fault", pd.Series(False, index=grp.index)).mean()

        # Anomaly rate
        if "combined_anomaly_score" in grp.columns:
            anomaly_rate = (grp["combined_anomaly_score"] > 0.5).mean()
        else:
            anomaly_rate = 0.0

        # Missing rate
        sensor_cols = ["temperature_c", "relative_humidity_pct", "pressure_hpa",
                       "wind_speed_kmh", "rainfall_mm"]
        available = [c for c in sensor_cols if c in grp.columns]
        if available:
            missing_rate = grp[available].isna().any(axis=1).mean()
        else:
            missing_rate = 0.0

        # Residual score (normalized by typical range)
        if "temperature_c_residual" in grp.columns:
            res = grp["temperature_c_residual"].abs().dropna()
            residual_score = float(np.clip(res.mean() / 10.0, 0, 1)) if len(res) > 0 else 0.0
        else:
            residual_score = 0.0

        # Noise score
        if "temperature_c_roll3_std" in grp.columns:
            noise = grp["temperature_c_roll3_std"].dropna()
            noise_score = float(np.clip(noise.mean() / 5.0, 0, 1)) if len(noise) > 0 else 0.0
        else:
            noise_score = 0.0

        penalty = (
            w["fault_rate"] * fault_rate
            + w["anomaly_rate"] * anomaly_rate
            + w["missing_rate"] * missing_rate
            + w["residual_score"] * residual_score
            + w["noise_score"] * noise_score
        )
        health_score = round(float(np.clip(100 * (1 - penalty), 0, 100)), 1)

        status = "CRITICAL"
        for s, threshold in STATUS_THRESHOLDS.items():
            if health_score >= threshold:
                status = s
                break

        results[str(station)] = {
            "station_id": str(station),
            "health_score": health_score,
            "status": status,
            "components": {
                "fault_rate": round(float(fault_rate), 4),
                "anomaly_rate": round(float(anomaly_rate), 4),
                "missing_rate": round(float(missing_rate), 4),
                "residual_score": round(float(residual_score), 4),
                "noise_score": round(float(noise_score), 4),
            },
        }
        logger.info(
            "Station %s health_score=%.1f status=%s", station, health_score, status
        )

    return results
