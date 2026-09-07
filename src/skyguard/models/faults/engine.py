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
                evidence.append(f"Relative humidity remained static while atmospheric baseline shifted")

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

        # Priority 5: Supervised classifier if available
        elif self.classifier is not None and self.classifier._model is not None:
            s_type = self.classifier.predict_fault_type(pd.Series(row))
            if s_type and s_type != "UNKNOWN":
                fault_type = s_type
                confidence = 0.80
                evidence.append(f"Supervised fault classifier pattern matches {s_type}")
                if fault_type == "DRIFT" and not pd.isna(temp_res):
                    evidence.append(f"Temperature residual: {temp_res:+.2f} °C")
                elif fault_type == "FREEZE" and not pd.isna(rh_res):
                    evidence.append(f"Humidity residual: {rh_res:+.2f}%")

        # Fallback
        else:
            inferred = infer_fault_type(row)
            if inferred != "UNKNOWN":
                fault_type = inferred
                confidence = 0.70
                evidence.append(f"Sensor heuristic rule matches {inferred}")
            else:
                fault_type = "UNKNOWN"
                confidence = 0.50
                evidence.append("Sensor telemetry anomalous but does not match single signature")

        # Add residual / baseline context if available
        if not pd.isna(temp_z) and abs(temp_z) > 2.5 and "temperature deviation" not in " ".join(evidence).lower():
            evidence.append(f"Temperature baseline deviation: {temp_z:+.2f} MAD")
        if not pd.isna(rh_z) and abs(rh_z) > 2.5 and "humidity" not in " ".join(evidence).lower():
            evidence.append(f"Relative humidity baseline deviation: {rh_z:+.2f} MAD")

        return {
            "fault_type": fault_type,
            "fault_confidence": round(confidence, 4),
            "fault_evidence": evidence,
        }
