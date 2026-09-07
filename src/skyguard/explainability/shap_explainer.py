"""SHAP explainability for tree-based models."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class SHAPExplainer:
    """Generates SHAP-based feature attributions for tree models."""

    def __init__(self, model: Any, feature_cols: list[str]) -> None:
        self._model = model
        self._feature_cols = feature_cols
        self._explainer: Any = None

    def fit(self, X_background: np.ndarray) -> "SHAPExplainer":
        try:
            import shap
            self._explainer = shap.TreeExplainer(self._model)
            logger.info("SHAP TreeExplainer fitted.")
        except ImportError:
            logger.warning("shap not installed; explanations will be feature-importance based.")
        except Exception as exc:
            logger.warning("SHAP init failed: %s", exc)
        return self

    def explain(self, X: np.ndarray, top_k: int = 5) -> list[dict[str, Any]]:
        """Return top-k feature attributions for each row in X."""
        explanations = []

        if self._explainer is not None:
            try:
                import shap
                shap_values = self._explainer.shap_values(X)
                # shap_values may be list (multi-class) or array
                if isinstance(shap_values, list):
                    # Use the class with highest predicted probability
                    shap_arr = np.array(shap_values)  # (n_classes, n_samples, n_features)
                    for i in range(X.shape[0]):
                        # Pick class with max absolute shap sum
                        class_sums = [np.abs(shap_arr[c, i]).sum() for c in range(len(shap_arr))]
                        best_class = int(np.argmax(class_sums))
                        sv = shap_arr[best_class, i]
                        explanations.append(self._top_k(sv, top_k))
                else:
                    for i in range(X.shape[0]):
                        explanations.append(self._top_k(shap_values[i], top_k))
                return explanations
            except Exception as exc:
                logger.warning("SHAP explain failed: %s", exc)

        # Fallback: use feature importances if available
        if hasattr(self._model, "feature_importances_"):
            fi = self._model.feature_importances_
            for _ in range(X.shape[0]):
                explanations.append(self._top_k(fi, top_k))
        else:
            for _ in range(X.shape[0]):
                explanations.append([])

        return explanations

    def _top_k(self, values: np.ndarray, k: int) -> list[dict[str, Any]]:
        idx = np.argsort(np.abs(values))[::-1][:k]
        return [
            {
                "feature": self._feature_cols[i] if i < len(self._feature_cols) else f"feat_{i}",
                "contribution": float(values[i]),
                "direction": "increases_fault" if values[i] > 0 else "decreases_fault",
            }
            for i in idx
        ]


def generate_human_explanation(
    prediction: str,
    confidence: float,
    top_features: list[dict[str, Any]],
    fault_type: str | None = None,
) -> list[str]:
    """Convert SHAP attributions into human-readable sentences."""
    lines = [
        f"Prediction: {prediction} (confidence: {confidence:.0%})",
    ]
    if fault_type and fault_type not in ("UNKNOWN", "NONE"):
        lines.append(f"Fault type: {fault_type}")

    lines.append("Top contributing signals:")
    for i, feat in enumerate(top_features, 1):
        name = feat["feature"].replace("_", " ")
        direction = "↑" if feat["contribution"] > 0 else "↓"
        lines.append(f"  {i}. {name} {direction} ({feat['contribution']:+.3f})")

    return lines
