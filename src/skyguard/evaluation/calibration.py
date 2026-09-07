"""Probability calibration using Platt scaling (sigmoid)."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import RobustScaler

logger = logging.getLogger(__name__)


class ProbabilityCalibrator:
    """Wraps a fitted classifier with Platt scaling calibration."""

    def __init__(self, base_classifier: Any, method: str = "sigmoid") -> None:
        self._base = base_classifier
        self._method = method
        self._calibrated: Any = None

    def fit(self, X_val: np.ndarray, y_val: np.ndarray) -> "ProbabilityCalibrator":
        """Fit calibration on validation data using the already-fitted base model."""
        self._calibrated = CalibratedClassifierCV(
            self._base, method=self._method, cv="prefit"
        )
        self._calibrated.fit(X_val, y_val)
        logger.info("Calibration fitted using method=%s on %d samples.", self._method, len(y_val))
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self._calibrated is None:
            return self._base.predict_proba(X)
        return self._calibrated.predict_proba(X)
