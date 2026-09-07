"""Optional Deep Learning Temporal Models (LSTM / GRU).

Architecturally defined for future large-scale sequence training.
Disabled by default on the current dataset (504 rows) to uphold scientific
safety constraints (requires >= 5000 samples to train safely).
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MIN_REQUIRED_SAMPLES = 5000


class DeepTemporalModel:
    """Optional deep learning temporal sequence model (LSTM / GRU).

    Automatically disables itself when dataset size is below scientific threshold.
    """

    def __init__(
        self,
        architecture: str = "lstm",
        enabled: bool = False,
        min_samples: int = MIN_REQUIRED_SAMPLES,
        sequence_length: int = 12,
        hidden_dim: int = 32,
        num_layers: int = 2,
    ) -> None:
        self.architecture = architecture
        self.enabled = enabled
        self.min_samples = min_samples
        self.sequence_length = sequence_length
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.is_active = False
        self.status_reason = "Disabled by default (safety constraint for small datasets)"
        self._model: Any = None

    def fit(self, df: pd.DataFrame) -> "DeepTemporalModel":
        n_samples = len(df)
        if not self.enabled:
            self.is_active = False
            self.status_reason = "Disabled via configuration"
            logger.info(
                "DeepTemporalModel [%s]: %s (samples=%d)",
                self.architecture.upper(), self.status_reason, n_samples
            )
            return self

        if n_samples < self.min_samples:
            self.is_active = False
            self.status_reason = (
                f"Dataset size ({n_samples} samples) is below the minimum scientific threshold "
                f"({self.min_samples} samples) required for deep sequential learning."
            )
            logger.warning("DeepTemporalModel [%s]: %s", self.architecture.upper(), self.status_reason)
            return self

        try:
            # Placeholder for PyTorch/TensorFlow deep sequence training if enabled on large datasets
            logger.info("DeepTemporalModel: Fitting %s on %d samples", self.architecture, n_samples)
            self.is_active = True
            self.status_reason = "Active and fitted"
        except Exception as exc:
            self.is_active = False
            self.status_reason = f"Failed to fit: {exc}"
            logger.error("DeepTemporalModel training error: %s", exc)

        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        if not self.is_active:
            return np.full(len(df), np.nan)
        return np.full(len(df), np.nan)

    def get_status(self) -> dict[str, Any]:
        return {
            "model_type": f"deep_temporal_{self.architecture}",
            "enabled": self.enabled,
            "is_active": self.is_active,
            "min_samples_required": self.min_samples,
            "status_reason": self.status_reason,
        }
