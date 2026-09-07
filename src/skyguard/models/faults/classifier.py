"""Supervised fault classifier — only trained when class counts are sufficient.

With the current dataset (Drift=13, Freeze=11, Spike=1), a supervised classifier
for Spike is NOT trained.  Only Drift vs Freeze is attempted if counts allow.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report
from sklearn.preprocessing import LabelEncoder, RobustScaler

from skyguard.models.faults.rules import infer_fault_type

logger = logging.getLogger(__name__)

MIN_SAMPLES_PER_CLASS = 5


class FaultClassifier:
    """Hybrid fault classifier: supervised where possible, rule-based otherwise."""

    def __init__(self, min_samples: int = MIN_SAMPLES_PER_CLASS) -> None:
        self._min_samples = min_samples
        self._model: Any = None
        self._scaler = RobustScaler()
        self._imputer = SimpleImputer(strategy="median")
        self._le = LabelEncoder()
        self._feature_cols: list[str] = []
        self._trainable_classes: list[str] = []
        self.val_metrics: dict[str, Any] = {}

    def fit(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame | None = None,
        fault_col: str = "fault_description",
        target_col: str = "ground_truth_label",
    ) -> "FaultClassifier":
        # Only use SENSOR_FAULT rows
        fault_df = train_df[train_df[target_col] == "SENSOR_FAULT"].copy()
        if len(fault_df) == 0:
            logger.warning("No SENSOR_FAULT rows in training data.")
            return self

        # Map fault descriptions to canonical types
        fault_df["fault_type"] = fault_df[fault_col].map(_map_fault_type)
        counts = fault_df["fault_type"].value_counts()
        logger.info("Fault type counts in training:\n%s", counts.to_string())

        # Only train on classes with enough samples
        self._trainable_classes = [
            cls for cls, cnt in counts.items() if cnt >= self._min_samples
        ]

        if len(self._trainable_classes) < 2:
            logger.warning(
                "Insufficient fault classes for supervised training "
                "(need ≥2 classes with ≥%d samples each). "
                "Will use rule-based classification only.",
                self._min_samples,
            )
            return self

        mask = fault_df["fault_type"].isin(self._trainable_classes)
        fault_df = fault_df[mask]

        exclude = {
            "ground_truth_label", "fault_description", "fault_type",
            "station_name", "timestamp", "station_id", "latitude", "longitude",
        }
        self._feature_cols = [
            c for c in fault_df.columns
            if pd.api.types.is_numeric_dtype(fault_df[c])
            and c not in exclude
            and not c.startswith("qf_")
            and fault_df[c].notna().sum() > 2
        ]

        mask_notna = fault_df["fault_type"].notna()
        X_tr = fault_df.loc[mask_notna, self._feature_cols].values
        y_tr = fault_df.loc[mask_notna, "fault_type"].values

        if len(X_tr) < 4:
            logger.warning("Too few fault samples after filtering.")
            return self

        self._le.fit(y_tr)
        y_enc = self._le.transform(y_tr)
        X_tr = self._imputer.fit_transform(X_tr)
        X_tr_s = self._scaler.fit_transform(X_tr)

        self._model = RandomForestClassifier(
            n_estimators=100, max_depth=6, class_weight="balanced", random_state=42, n_jobs=-1
        )
        self._model.fit(X_tr_s, y_enc)
        logger.info("FaultClassifier trained on classes: %s", self._trainable_classes)

        if val_df is not None:
            val_fault = val_df[val_df[target_col] == "SENSOR_FAULT"].copy()
            if len(val_fault) > 0:
                val_fault["fault_type"] = val_fault[fault_col].map(_map_fault_type)
                val_fault = val_fault[val_fault["fault_type"].isin(self._trainable_classes)]
                if len(val_fault) > 0:
                    mask_v = val_fault["fault_type"].notna()
                    X_v = val_fault.loc[mask_v, self._feature_cols].values
                    X_v = self._imputer.transform(X_v)
                    X_v = self._scaler.transform(X_v)
                    y_v = self._le.transform(val_fault.loc[mask_v, "fault_type"].values)
                    preds = self._model.predict(X_v)
                    self.val_metrics = {
                        "report": classification_report(
                            y_v, preds,
                            target_names=self._le.classes_,
                            output_dict=True,
                            zero_division=0,
                        )
                    }

        return self

    def predict_fault_type(self, row: pd.Series) -> str:
        """Predict fault type for a single SENSOR_FAULT observation."""
        if self._model is not None and self._feature_cols:
            feat_vals = [row.get(c, np.nan) for c in self._feature_cols]
            X = np.array([feat_vals])
            X = self._imputer.transform(X)
            X = self._scaler.transform(X)
            enc = self._model.predict(X)[0]
            return str(self._le.inverse_transform([enc])[0])

        # Fall back to rule-based
        return infer_fault_type(row)


def _map_fault_type(description: str) -> str:
    if pd.isna(description) or description == "None":
        return "UNKNOWN"
    desc = str(description).lower()
    if "drift" in desc or "calibration" in desc:
        return "DRIFT"
    if "freeze" in desc or "zero variance" in desc:
        return "FREEZE"
    if "spike" in desc or "noise spike" in desc:
        return "SPIKE"
    if "communication" in desc:
        return "COMMUNICATION_FAILURE"
    return "UNKNOWN"
