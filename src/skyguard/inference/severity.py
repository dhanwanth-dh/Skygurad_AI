"""Severity engine — transparent, rule-based severity scoring."""

from __future__ import annotations


SEVERITY_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def compute_severity(
    prediction: str,
    confidence: float,
    anomaly_score: float,
    fault_type: str | None = None,
    anomaly_score_thresholds: tuple[float, float, float] = (0.40, 0.65, 0.85),
) -> str:
    """Compute severity level based on prediction, confidence, and anomaly score.

    Severity is independent of confidence:
    - Confidence = how certain the model is.
    - Severity = how serious the issue is.

    Rules:
    1. NORMAL → LOW always.
    2. GENUINE_EXTREME → MEDIUM to HIGH based on anomaly score.
    3. SENSOR_FAULT → MEDIUM to CRITICAL based on anomaly score and fault type.
    """
    if prediction == "NORMAL":
        return "LOW"

    med_t, high_t, crit_t = anomaly_score_thresholds

    if prediction == "GENUINE_EXTREME":
        if anomaly_score >= high_t:
            return "HIGH"
        if anomaly_score >= med_t:
            return "MEDIUM"
        return "LOW"

    # SENSOR_FAULT
    if fault_type in ("DRIFT", "FREEZE"):
        # Persistent faults are more severe
        if anomaly_score >= crit_t:
            return "CRITICAL"
        if anomaly_score >= high_t:
            return "HIGH"
        return "MEDIUM"

    if fault_type == "SPIKE":
        # Single-point spike — HIGH but not CRITICAL unless very large
        if anomaly_score >= crit_t:
            return "HIGH"
        return "MEDIUM"

    # Unknown fault type
    if anomaly_score >= crit_t:
        return "HIGH"
    if anomaly_score >= med_t:
        return "MEDIUM"
    return "LOW"
