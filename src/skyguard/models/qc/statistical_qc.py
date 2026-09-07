"""Classical Statistical Quality Control (QC) for AWS observations.

Implements 10 meteorological quality checks alongside machine learning:
1. Physical Bounds check (temperature, humidity, pressure, wind, rain)
2. Rate-of-Change check (excessive delta between successive hourly readings)
3. Rolling Mean Deviation check (short-term rolling deviation)
4. Rolling Standard Deviation / Volatility check
5. Robust Z-score check (hourly MAD deviation)
6. MAD-based Spike detection (isolated extreme excursion + recovery)
7. Frozen-Value detection (consecutive near-zero variance)
8. Temporal Gap detection (time_since_prev_obs > expected window)
9. Duplicate Timestamp detection
10. Cross-Sensor Consistency check (e.g., supersaturation or physical conflicts)

Produces a normalized statistical_anomaly_score and structured qc_evidence list.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_BOUNDS = {
    "temperature_c": (-10.0, 60.0),
    "relative_humidity_pct": (0.0, 100.0),
    "pressure_hpa": (870.0, 1084.0),
    "wind_speed_kmh": (0.0, 200.0),
    "rainfall_mm": (0.0, 500.0),
}

DEFAULT_MAX_RATES = {
    "temperature_c": 5.0,        # max 5 °C per hour
    "relative_humidity_pct": 30.0, # max 30% per hour
    "pressure_hpa": 10.0,         # max 10 hPa per hour
    "wind_speed_kmh": 40.0,       # max 40 km/h per hour
}


class StatisticalQC:
    """Performs comprehensive meteorological quality control checks on observations."""

    def __init__(
        self,
        bounds: dict[str, tuple[float, float]] | None = None,
        max_rates: dict[str, float] | None = None,
        freeze_variance_threshold: float = 0.01,
        freeze_min_consecutive: int = 3,
        spike_zscore_threshold: float = 4.0,
        drift_consecutive_threshold: int = 5,
        temporal_gap_hours: float = 3.0,
    ) -> None:
        self.bounds = bounds or DEFAULT_BOUNDS.copy()
        self.max_rates = max_rates or DEFAULT_MAX_RATES.copy()
        self.freeze_variance_threshold = freeze_variance_threshold
        self.freeze_min_consecutive = freeze_min_consecutive
        self.spike_zscore_threshold = spike_zscore_threshold
        self.drift_consecutive_threshold = drift_consecutive_threshold
        self.temporal_gap_hours = temporal_gap_hours

    def check_observation(self, row: pd.Series | dict[str, Any]) -> dict[str, Any]:
        """Perform QC checks on a single observation. Returns flags, score, and evidence."""
        evidence: list[str] = []
        violations: list[str] = []
        penalty: float = 0.0

        # 1. Physical bounds
        for col, (low, high) in self.bounds.items():
            val = row.get(col, np.nan)
            if not pd.isna(val) and (val < low or val > high):
                violations.append(f"{col}_out_of_bounds")
                evidence.append(f"{col} ({val}) outside physical bounds [{low}, {high}]")
                penalty += 0.40

        # 2. Rate-of-change (deltas)
        for col, max_rate in self.max_rates.items():
            delta_col = f"{col}_delta"
            delta_val = row.get(delta_col, np.nan)
            if not pd.isna(delta_val) and abs(delta_val) > max_rate:
                violations.append(f"{col}_rate_of_change_high")
                evidence.append(f"{col} rate of change ({abs(delta_val):.2f}) exceeds max allowed ({max_rate})")
                penalty += 0.25

        # 3. Rolling mean deviation
        for col in ["temperature_c", "pressure_hpa"]:
            dev_col = f"{col}_deviation"
            dev_val = row.get(dev_col, np.nan)
            if not pd.isna(dev_val) and abs(dev_val) > (4.0 if col == "temperature_c" else 15.0):
                violations.append(f"{col}_large_baseline_deviation")
                evidence.append(f"{col} deviation from station baseline is {dev_val:+.2f}")
                penalty += 0.20

        # 4. Rolling standard deviation / volatility
        temp_std = row.get("temperature_c_roll3_std", np.nan)
        if not pd.isna(temp_std) and temp_std > 4.0:
            violations.append("temperature_c_high_volatility")
            evidence.append(f"Temperature rolling volatility is unusually high ({temp_std:.2f} °C)")
            penalty += 0.15

        # 5. Robust z-score
        for col in ["temperature_c", "relative_humidity_pct", "pressure_hpa"]:
            z_col = f"{col}_robust_z"
            z_val = row.get(z_col, np.nan)
            if not pd.isna(z_val) and abs(z_val) >= 3.5:
                violations.append(f"{col}_robust_z_high")
                evidence.append(f"{col} robust Z-score is {z_val:+.2f}")
                penalty += 0.20

        # 6. Spike detection flag
        if row.get("rule_spike", False):
            violations.append("spike_detected")
            evidence.append("Single-point extreme spike detected followed by recovery")
            penalty += 0.35

        # 7. Frozen-value flag
        if row.get("rule_freeze", False):
            violations.append("freeze_detected")
            evidence.append(f"Near-zero variance across {self.freeze_min_consecutive}+ observations (frozen sensor)")
            penalty += 0.35

        # 8. Temporal gap
        time_since_prev = row.get("time_since_prev_obs", np.nan)
        if not pd.isna(time_since_prev) and time_since_prev > self.temporal_gap_hours:
            violations.append("temporal_gap")
            evidence.append(f"Observation follows a temporal data gap of {time_since_prev:.1f} hours")
            penalty += 0.15

        # 9. Duplicate check (from metadata if flagged)
        if row.get("is_duplicate_timestamp", False):
            violations.append("duplicate_timestamp")
            evidence.append("Duplicate station timestamp detected")
            penalty += 0.30

        # 10. Cross-sensor physical consistency
        temp = row.get("temperature_c", np.nan)
        rh = row.get("relative_humidity_pct", np.nan)
        rain = row.get("rainfall_mm", np.nan)
        if not pd.isna(temp) and not pd.isna(rh) and not pd.isna(rain):
            # Heavy rain during extremely low humidity is physically inconsistent
            if rain > 10.0 and rh < 25.0:
                violations.append("cross_sensor_rain_humidity_inconsistent")
                evidence.append(f"Rainfall ({rain} mm) inconsistent with low humidity ({rh}%)")
                penalty += 0.25

        score = float(np.clip(penalty, 0.0, 1.0))

        return {
            "statistical_anomaly_score": round(score, 4),
            "qc_passed": len(violations) == 0,
            "qc_violations": violations,
            "qc_evidence": evidence,
        }

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply statistical QC checks across entire DataFrame."""
        df = df.copy()
        scores = []
        violations_list = []
        passed_list = []

        for _, row in df.iterrows():
            res = self.check_observation(row)
            scores.append(res["statistical_anomaly_score"])
            violations_list.append(", ".join(res["qc_violations"]))
            passed_list.append(res["qc_passed"])

        df["statistical_anomaly_score"] = scores
        df["qc_violations"] = violations_list
        df["qc_passed"] = passed_list
        return df


def run_qc_checks(df: pd.DataFrame) -> pd.DataFrame:
    qc = StatisticalQC()
    return qc.transform(df)
