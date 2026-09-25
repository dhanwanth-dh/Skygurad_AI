"""Master Evidence Fusion Engine.

Synthesizes multi-model evidence from all analytical pipelines:
- Regression ensemble expected values and model disagreement
- 6-detector unsupervised anomaly consensus
- Statistical QC checks and violation penalties
- Sensor fault rule and classification engines
- Genuine meteorological event spatial consistency
- Model coverage and uncertainty quantification

Produces final scientific classification, confidence level, uncertainty score,
severity rating, transparent explanations, and actionable recommendations.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from skyguard.inference.severity import compute_severity

logger = logging.getLogger(__name__)


class MasterEvidenceFusion:
    """Central intelligence layer performing transparent multi-model evidence fusion."""

    def __init__(
        self,
        sensor_fault_threshold: float = 0.40,
        genuine_extreme_threshold: float = 0.35,
        confidence_min_correction: float = 0.80,
    ) -> None:
        self.sensor_fault_threshold = sensor_fault_threshold
        self.genuine_extreme_threshold = genuine_extreme_threshold
        self.confidence_min_correction = confidence_min_correction

    def fuse(
        self,
        observation: dict[str, Any] | pd.Series,
        expected_results: dict[str, Any],
        anomaly_results: dict[str, Any],
        qc_results: dict[str, Any],
        fault_results: dict[str, Any],
        event_results: dict[str, Any],
        model_coverage_ratio: float = 1.0,
    ) -> dict[str, Any]:
        """Synthesize all model outputs into a robust, explainable decision."""
        # 1. Extract Anomaly Evidence
        combined_anomaly_score = float(np.atleast_1d(anomaly_results.get("combined_anomaly_score", 0.0))[0])
        anomaly_consensus = float(np.atleast_1d(anomaly_results.get("consensus_score", 0.0))[0])
        models_agreeing = int(np.atleast_1d(anomaly_results.get("models_agreeing", 0))[0])
        total_anomaly_models = int(np.atleast_1d(anomaly_results.get("total_models", 6))[0])
        anomaly_ratio = float(np.atleast_1d(anomaly_results.get("agreement_ratio", 0.0))[0])

        # 2. Extract Regression Disagreement
        temp_agreement = float(expected_results.get("temp_agreement", 1.0))
        humidity_agreement = float(expected_results.get("humidity_agreement", 1.0))
        pressure_agreement = float(expected_results.get("pressure_agreement", 1.0))
        avg_regression_agreement = (temp_agreement + humidity_agreement + pressure_agreement) / 3.0
        regression_disagreement = 1.0 - avg_regression_agreement

        # 3. Extract QC & Residual Evidence
        qc_score = float(qc_results.get("statistical_anomaly_score", 0.0))
        qc_evidence = qc_results.get("qc_evidence", [])

        # 4. Extract Fault & Weather Event Evidence
        fault_type = str(fault_results.get("fault_type", "NONE"))
        fault_confidence = float(fault_results.get("fault_confidence", 0.0))
        fault_evidence = fault_results.get("fault_evidence", [])

        genuine_event_score = float(event_results.get("genuine_event_score", 0.0))
        genuine_event_evidence = event_results.get("genuine_event_evidence", [])

        # 5. Calculate Master Fused Anomaly Score
        final_anomaly_score = float(np.clip(
            0.45 * combined_anomaly_score +
            0.30 * qc_score +
            0.25 * max(combined_anomaly_score, qc_score if qc_score > 0.5 else 0.0),
            0.0, 1.0
        ))

        # 6. Calculate Uncertainty Score
        anomaly_detector_conflict = 1.0 - abs(anomaly_ratio - 0.5) * 2.0
        evidence_conflict = 0.5 if (fault_confidence > 0.5 and genuine_event_score > 0.5) else 0.0
        coverage_penalty = max(0.0, 1.0 - model_coverage_ratio)

        # In genuine weather events, regression disagreement is physical (cooling/rain), not epistemic uncertainty
        effective_reg_disagreement = regression_disagreement * (0.3 if genuine_event_score >= 0.40 else 1.0)

        raw_uncertainty = (
            0.35 * effective_reg_disagreement +
            0.25 * anomaly_detector_conflict +
            0.25 * coverage_penalty +
            0.15 * evidence_conflict
        )
        uncertainty_score = float(np.clip(raw_uncertainty, 0.02, 0.95))

        # Model Agreement overall
        overall_model_agreement = float(np.clip(
            0.5 * avg_regression_agreement + 0.5 * (1.0 - anomaly_detector_conflict),
            0.0, 1.0
        ))

        # 7. Final Decision Classification
        prediction = "NORMAL"
        class_probs = {"NORMAL": 0.90, "GENUINE_EXTREME": 0.05, "SENSOR_FAULT": 0.05}

        is_hard_fault = fault_type in ("FREEZE", "SPIKE", "COMMUNICATION_FAILURE")

        # Case A: Genuine Meteorological Extreme
        if genuine_event_score >= self.genuine_extreme_threshold and not is_hard_fault and (genuine_event_score >= fault_confidence or fault_type == "NONE"):
            prediction = "GENUINE_EXTREME"
            confidence = float(np.clip(0.65 + genuine_event_score * 0.30 - uncertainty_score * 0.15, 0.60, 0.98))
            class_probs = {
                "GENUINE_EXTREME": round(confidence, 4),
                "SENSOR_FAULT": round((1.0 - confidence) * 0.4, 4),
                "NORMAL": round((1.0 - confidence) * 0.6, 4),
            }

        # Case B: Hardware Sensor Fault
        elif (fault_type != "NONE" and fault_type != "UNKNOWN" and fault_confidence >= 0.40) or (is_hard_fault) or (qc_score >= 0.50 and genuine_event_score < 0.30):
            prediction = "SENSOR_FAULT"
            base_conf = max(fault_confidence, final_anomaly_score)
            confidence = float(np.clip(base_conf * 0.90 + 0.05 - uncertainty_score * 0.15, 0.55, 0.98))
            class_probs = {
                "SENSOR_FAULT": round(confidence, 4),
                "GENUINE_EXTREME": round((1.0 - confidence) * 0.3, 4),
                "NORMAL": round((1.0 - confidence) * 0.7, 4),
            }

        # Case C: Low Anomaly Evidence -> Normal
        elif final_anomaly_score < self.sensor_fault_threshold and qc_score < 0.35 and fault_type == "NONE":
            prediction = "NORMAL"
            confidence = float(np.clip(1.0 - final_anomaly_score * 1.2, 0.60, 0.99))
            class_probs = {
                "NORMAL": round(confidence, 4),
                "GENUINE_EXTREME": round((1.0 - confidence) * 0.4, 4),
                "SENSOR_FAULT": round((1.0 - confidence) * 0.6, 4),
            }

        # Case D: Ambiguous / Indeterminate
        else:
            if genuine_event_score >= 0.30:
                prediction = "GENUINE_EXTREME"
                confidence = 0.65
                class_probs = {"GENUINE_EXTREME": 0.65, "SENSOR_FAULT": 0.20, "NORMAL": 0.15}
            elif uncertainty_score > 0.60:
                prediction = "UNKNOWN"
                confidence = 0.40
                class_probs = {"NORMAL": 0.40, "SENSOR_FAULT": 0.35, "GENUINE_EXTREME": 0.25}
            else:
                prediction = "NORMAL"
                confidence = 0.65
                class_probs = {"NORMAL": 0.65, "GENUINE_EXTREME": 0.20, "SENSOR_FAULT": 0.15}

        # Confidence Level categorization
        if confidence >= 0.80 and uncertainty_score <= 0.35:
            confidence_level = "HIGH"
        elif confidence >= 0.55 and uncertainty_score <= 0.55:
            confidence_level = "MEDIUM"
        else:
            confidence_level = "LOW"

        # 8. Severity
        severity = compute_severity(
            prediction=prediction,
            confidence=confidence,
            anomaly_score=final_anomaly_score,
            fault_type=fault_type if prediction == "SENSOR_FAULT" else None,
        )

        # 9. Top Reasons & Explanation Synthesis
        top_reasons: list[str] = []

        if prediction == "GENUINE_EXTREME":
            top_reasons.extend(genuine_event_evidence[:3])
            if models_agreeing > 0:
                top_reasons.append(f"{models_agreeing}/{total_anomaly_models} anomaly detectors confirm significant atmospheric deviation")

        elif prediction == "SENSOR_FAULT":
            top_reasons.extend(fault_evidence[:3])
            if models_agreeing > 0:
                top_reasons.append(f"{models_agreeing}/{total_anomaly_models} anomaly models flag statistical outlier")
            if qc_evidence:
                top_reasons.append(qc_evidence[0])

        elif prediction == "NORMAL":
            top_reasons.append("All sensor observations within normal historical climatology baselines")
            if models_agreeing == 0:
                top_reasons.append("Unsupervised anomaly detectors find no outlier evidence (0/6 consensus)")
            top_reasons.append("High cross-sensor regression and neighbor spatial agreement")

        elif prediction == "UNKNOWN":
            top_reasons.append("Conflicting evidence detected across anomaly and spatial engines")
            top_reasons.append(f"Model disagreement uncertainty is high ({uncertainty_score:.2f})")

        # 10. Recommended Action
        if prediction == "GENUINE_EXTREME":
            recommended_action = "Issue meteorological alert. Confirm radar and satellite ground truth."
        elif prediction == "SENSOR_FAULT":
            if fault_type == "DRIFT":
                recommended_action = "Schedule calibration audit. Recalibrate sensor offset baseline."
            elif fault_type == "FREEZE":
                recommended_action = "Inspect transducer hardware for physical blockage or power stall."
            elif fault_type == "SPIKE":
                recommended_action = "Transient spike detected. Verify line noise or transient surge."
            elif fault_type == "COMMUNICATION_FAILURE":
                recommended_action = "Check telemetry modem, solar power budget, and cellular link."
            else:
                recommended_action = "Inspect station telemetry and dispatch field maintenance if error persists."
        elif prediction == "NORMAL":
            recommended_action = "Routine monitoring. Data quality verified."
        else:
            recommended_action = "Collect additional consecutive observations to resolve ambiguity."

        return {
            "prediction": prediction,
            "confidence": round(confidence, 4),
            "confidence_level": confidence_level,
            "uncertainty_score": round(uncertainty_score, 4),
            "anomaly_score": round(final_anomaly_score, 4),
            "model_agreement": round(overall_model_agreement, 4),
            "model_coverage": f"{int(model_coverage_ratio * total_anomaly_models)}/{total_anomaly_models} active",
            "model_coverage_ratio": round(model_coverage_ratio, 2),
            "class_probabilities": class_probs,
            "fault_type": fault_type if prediction == "SENSOR_FAULT" else "NONE",
            "fault_confidence": round(fault_confidence, 4) if prediction == "SENSOR_FAULT" else 0.0,
            "fault_evidence": fault_evidence,
            "genuine_event_score": round(genuine_event_score, 4),
            "genuine_event_evidence": genuine_event_evidence,
            "severity": severity,
            "top_reasons": top_reasons,
            "recommended_action": recommended_action,
        }
