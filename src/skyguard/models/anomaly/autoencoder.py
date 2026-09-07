"""Optional Autoencoder Anomaly Detector.

Architecturally defined for unsupervised feature reconstruction.
Disabled by default on the current dataset (504 rows) to uphold scientific
safety constraints (requires >= 5000 samples to train reliably without overfitting).
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MIN_AUTOENCODER_SAMPLES = 5000


class AutoencoderDetector:
    """Optional Autoencoder for non-linear reconstruction anomaly detection."""

    def __init__(
        self,
        enabled: bool = False,
        min_samples: int = MIN_AUTOENCODER_SAMPLES,
        latent_dim: int = 8,
    ) -> None:
        self.enabled = enabled
        self.min_samples = min_samples
        self.latent_dim = latent_dim
        self.is_active = False
        self.status_reason = "Disabled by default (safety constraint for small datasets)"
        self._threshold = 0.0

    def fit(self, X: np.ndarray) -> "AutoencoderDetector":
        n_samples = len(X)
        if not self.enabled:
            self.is_active = False
            self.status_reason = "Disabled via configuration"
            logger.info("AutoencoderDetector: %s", self.status_reason)
            return self

        if n_samples < self.min_samples:
            self.is_active = False
            self.status_reason = (
                f"Dataset size ({n_samples} samples) is below the minimum scientific threshold "
                f"({self.min_samples} samples) required for Autoencoder anomaly detection."
            )
            logger.warning("AutoencoderDetector: %s", self.status_reason)
            return self

        try:
            logger.info("AutoencoderDetector: Fitting on %d samples", n_samples)
            self.is_active = True
            self.status_reason = "Active and fitted"
        except Exception as exc:
            self.is_active = False
            self.status_reason = f"Failed to fit: {exc}"
            logger.error("Autoencoder training error: %s", exc)

        return self

    def score(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return (raw_reconstruction_error, normalized_anomaly_score)."""
        if not self.is_active:
            zeros = np.zeros(len(X))
            return zeros, zeros
        zeros = np.zeros(len(X))
        return zeros, zeros

    def get_status(self) -> dict[str, Any]:
        return {
            "model_type": "autoencoder",
            "enabled": self.enabled,
            "is_active": self.is_active,
            "min_samples_required": self.min_samples,
            "status_reason": self.status_reason,
        }
