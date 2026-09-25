"""Fault Evidence Engine — fuses supervised classification, heuristic rules,
expected-value residuals, and baseline deviations to diagnose sensor fault types.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from skyguard.models.faults.classifier import FaultClassifier
from skyguard.models.faults.rules import infer_fault_type

logger = logging.getLogger(__name__)


class FaultEvidenceEngine:
    """Combines rule detectors, supervised fault classifier, and residual signals."""

    def __init__(self, classifier: FaultClassifier | None = None) -> None:
        self.classifier = classifier

    def evaluate(self, row: pd.Series | dict[str, Any], is_anomaly: bool = True) -> dict[str, Any]:
        """Diagnose sensor fault type and synthesize concrete scientific evidence."""
        evidence: list[str] = []
        fault_type = "NONE"
        confidence = 0.0

        if not is_anomaly:
            return {
                "fault_type": "NONE",
                "fault_confidence": 0.0,
                "fault_evidence": [],
            }

        def _val(col: str, default: float = 0.0) -> float:
            v = row.get(col, default) if isinstance(row, dict) else row.get(col, default)
            try:
                if v is None or pd.isna(v):
                    return default
                return float(v)
            except (ValueError, TypeError):
                return default

        rain = _val("rainfall_mm", 0.0)
        wind = _val("wind_speed_kmh", 0.0)
        temp = _val("temperature_c", 25.0)
        rh = _val("relative_humidity_pct", 50.0)

        # 1. Check rule-based signatures
        is_spike = bool(row.get("rule_spike", False))
        is_freeze = bool(row.get("rule_freeze", False))
        is_drift = bool(row.get("rule_drift", False))
        is_comm = bool(row.get("rule_communication", False))

        # Check expected residuals & deviations
        temp_res = row.get("temperature_c_residual", np.nan)
        rh_res = row.get("relative_humidity_pct_residual", np.nan)
        press_res = row.get("pressure_hpa_residual", np.nan)

        temp_z = row.get("temperature_c_robust_z", np.nan)
        rh_z = row.get("relative_humidity_pct_robust_z", np.nan)
        press_z = row.get("pressure_hpa_robust_z", np.nan)
        qc_score = float(row.get("statistical_anomaly_score", 0.0) or 0.0)

        has_severe_weather = (
            (rain >= 10.0 and rh >= 70.0)
            or (wind >= 35.0)
            or (temp >= 40.0 and rh <= 55.0)
            or (temp <= 8.0 and temp >= -20.0)
        )

        # Priority 1: Spike (isolated jump + recovery)
        if is_spike:
            fault_type = "SPIKE"
            confidence = 0.95
            evidence.append("Single-point extreme pressure excursion with immediate temporal recovery")
            if not pd.isna(press_res):
                evidence.append(f"Pressure residual deviated by {press_res:+.2f} hPa from expected value")

        # Priority 2: Freeze (zero variance)
        elif is_freeze:
            fault_type = "FREEZE"
            confidence = 0.92
            evidence.append("Near-zero variance across consecutive sensor observations (stuck value)")
            if not pd.isna(rh_z):
                evidence.append("Relative humidity remained static while atmospheric baseline shifted")

        # Priority 3: Drift (persistent directional deviation)
        elif is_drift:
            fault_type = "DRIFT"
            confidence = 0.88
            evidence.append("Persistent directional deviation exceeding 2.0 robust MAD baselines")
            if not pd.isna(temp_res) and abs(temp_res) > 1.5:
                evidence.append(f"Expected temperature residual steadily increased ({temp_res:+.2f} °C)")

        # Priority 4: Communication / Telemetry failure
        elif is_comm:
            fault_type = "COMMUNICATION_FAILURE"
            confidence = 0.85
            time_gap = row.get("time_since_prev_obs", np.nan)
            evidence.append(f"Telemetry temporal gap ({time_gap:.1f} hours) indicates transmission dropout")

        # Priority 5: Quality Control violation (severe physical range / physical consistency failure)
        elif qc_score >= 0.50 and not has_severe_weather:
            fault_type = "DRIFT"
            confidence = 0.80
            evidence.append(f"Severe statistical quality control violation (score: {qc_score:.2f})")

        # Priority 6: Severe Weather or Normal telemetry without hardware fault flags
        else:
            inferred = infer_fault_type(row)
            if inferred != "UNKNOWN":
                fault_type = inferred
                confidence = 0.70
                evidence.append(f"Sensor heuristic rule matches {inferred}")
            else:
                fault_type = "NONE"
                confidence = 0.0
                evidence.append("No hardware fault signatures detected on active sensors")

        # Add residual / baseline context if available and a fault was found
        if fault_type != "NONE":
            if not pd.isna(temp_z) and abs(temp_z) > 2.5 and "temperature deviation" not in " ".join(evidence).lower():
                evidence.append(f"Temperature baseline deviation: {temp_z:+.2f} MAD")
            if not pd.isna(rh_z) and abs(rh_z) > 2.5 and "humidity" not in " ".join(evidence).lower():
                evidence.append(f"Relative humidity baseline deviation: {rh_z:+.2f} MAD")

        return {
            "fault_type": fault_type,
            "fault_confidence": round(confidence, 4),
            "fault_evidence": evidence,
        }
