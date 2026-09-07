"""Rule-based fault signature detection.

Implements transparent heuristic fault detectors:
- FREEZE: near-zero variance across consecutive readings
- SPIKE: isolated single-point deviation followed by immediate recovery
- DRIFT: persistent directional deviation from station baseline
- COMMUNICATION_FAILURE: temporal gaps or missing sensor telemetry
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def detect_freeze(
    df: pd.DataFrame,
    col: str = "relative_humidity_pct",
    variance_threshold: float = 0.01,
    min_consecutive: int = 3,
) -> pd.Series:
    """Detect frozen sensor: near-zero variance over consecutive observations."""
    src = f"{col}_clean" if f"{col}_clean" in df.columns else col
    result = pd.Series(False, index=df.index)

    for station, grp in df.groupby("station_id"):
        vals = grp[src].values
        frozen = np.zeros(len(vals), dtype=bool)
        for i in range(min_consecutive - 1, len(vals)):
            window = vals[i - min_consecutive + 1: i + 1]
            if np.nanvar(window) < variance_threshold:
                frozen[i - min_consecutive + 1: i + 1] = True
        result.loc[grp.index] = frozen

    return result


def detect_spike(
    df: pd.DataFrame,
    col: str = "pressure_hpa",
    zscore_threshold: float = 4.0,
) -> pd.Series:
    """Detect single-point spike: large deviation followed by recovery."""
    src = f"{col}_clean" if f"{col}_clean" in df.columns else col
    result = pd.Series(False, index=df.index)

    for station, grp in df.groupby("station_id"):
        vals = grp[src].values
        if len(vals) < 3:
            continue
        med = np.nanmedian(vals)
        mad = np.nanmedian(np.abs(vals - med))
        scale = mad * 1.4826
        if scale < 1e-6:
            scale = float(np.nanstd(vals))
        if scale < 1e-6:
            continue
        z = np.abs(vals - med) / scale
        spike = np.zeros(len(vals), dtype=bool)
        for i in range(1, len(vals) - 1):
            if z[i] > zscore_threshold and z[i - 1] < zscore_threshold and z[i + 1] < zscore_threshold:
                spike[i] = True
        result.loc[grp.index] = spike

    return result


def detect_drift(
    df: pd.DataFrame,
    col: str = "temperature_c",
    consecutive_threshold: int = 5,
    deviation_threshold: float = 2.0,
) -> pd.Series:
    """Detect drift: persistent directional deviation from baseline."""
    result = pd.Series(False, index=df.index)
    robust_z_col = f"{col}_robust_z"

    if robust_z_col not in df.columns:
        return result

    for station, grp in df.groupby("station_id"):
        z = grp[robust_z_col].values
        drift = np.zeros(len(z), dtype=bool)
        count = 0
        for i, zi in enumerate(z):
            if not np.isnan(zi) and abs(zi) > deviation_threshold:
                count += 1
            else:
                count = 0
            if count >= consecutive_threshold:
                drift[max(0, i - count + 1): i + 1] = True
        result.loc[grp.index] = drift

    return result


def detect_communication_failure(
    df: pd.DataFrame,
    gap_hours_threshold: float = 3.0,
) -> pd.Series:
    """Detect telemetry communication failure or extreme temporal gap."""
    result = pd.Series(False, index=df.index)
    if "time_since_prev_obs" in df.columns:
        result = df["time_since_prev_obs"] > gap_hours_threshold
    return result


def apply_fault_rules(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all rule-based fault detectors and add flag columns."""
    df = df.copy()
    df["rule_freeze"] = detect_freeze(df)
    df["rule_spike"] = detect_spike(df)
    df["rule_drift"] = detect_drift(df)
    df["rule_communication"] = detect_communication_failure(df)
    df["rule_any_fault"] = (
        df["rule_freeze"] | df["rule_spike"] | df["rule_drift"] | df["rule_communication"]
    )
    return df


def infer_fault_type(row: pd.Series | dict) -> str:
    """Infer fault type from rule flags for a single observation."""
    if row.get("rule_spike", False):
        return "SPIKE"
    if row.get("rule_freeze", False):
        return "FREEZE"
    if row.get("rule_drift", False):
        return "DRIFT"
    if row.get("rule_communication", False):
        return "COMMUNICATION_FAILURE"
    return "UNKNOWN"
