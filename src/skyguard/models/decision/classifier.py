"""Main decision classifier — NORMAL / GENUINE_EXTREME / SENSOR_FAULT.

Benchmarks Logistic Regression, Random Forest, and XGBoost.
Selects based on macro F1 on validation set.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    auc,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
)
from sklearn.preprocessing import LabelEncoder, RobustScaler

logger = logging.getLogger(__name__)

EXCLUDE_COLS = {
    "ground_truth_label", "fault_description", "station_name",
    "timestamp", "station_id", "latitude", "longitude",
}
EXCLUDE_PREFIXES = ("qf_",)

# All possible classes — ensures LabelEncoder is always consistent
ALL_CLASSES = sorted(["NORMAL", "GENUINE_EXTREME", "SENSOR_FAULT"])


def _decision_feature_cols(df: pd.DataFrame) -> list[str]:
    return [
        c for c in df.columns
        if pd.api.types.is_numeric_dtype(df[c])
        and c not in EXCLUDE_COLS
        and not any(c.startswith(p) for p in EXCLUDE_PREFIXES)
    ]


class DecisionClassifier:
    """Multi-class classifier for NORMAL / GENUINE_EXTREME / SENSOR_FAULT."""

    def __init__(self, random_state: int = 42) -> None:
        self._random_state = random_state
        self._model: Any = None
        self._scaler = RobustScaler()
        self._imputer = SimpleImputer(strategy="median")
        self._le = LabelEncoder()
        self._le.fit(ALL_CLASSES)  # always fit on all 3 classes
        self._feature_cols: list[str] = []
        self._best_name: str = ""
        self._xgb_inv_map: dict | None = None
        self.val_metrics: dict[str, Any] = {}

    def _build_candidates(self) -> dict[str, Any]:
        rs = self._random_state
        candidates: dict[str, Any] = {
            "logistic_regression": LogisticRegression(
                max_iter=1000, class_weight="balanced", random_state=rs, C=0.5
            ),
            "random_forest": RandomForestClassifier(
                n_estimators=150, max_depth=8, min_samples_leaf=2,
                class_weight="balanced", random_state=rs, n_jobs=-1,
            ),
        }
        try:
            from xgboost import XGBClassifier
            # XGBoost needs contiguous 0-indexed labels; we remap internally
            candidates["xgboost"] = XGBClassifier(
                n_estimators=150, max_depth=5, learning_rate=0.08,
                subsample=0.8, colsample_bytree=0.8,
                eval_metric="mlogloss", random_state=rs, n_jobs=-1, verbosity=0,
            )
        except ImportError:
            logger.info("XGBoost not available; skipping.")
        return candidates

    def _remap_labels(self, y: np.ndarray) -> tuple[np.ndarray, dict]:
        """Remap arbitrary integer labels to contiguous 0-indexed for XGBoost."""
        unique = sorted(set(y.tolist()))
        mapping = {v: i for i, v in enumerate(unique)}
        inv_mapping = {i: v for v, i in mapping.items()}
        return np.array([mapping[v] for v in y]), inv_mapping

    def _prepare(self, df: pd.DataFrame, target_col: str) -> tuple[np.ndarray, np.ndarray]:
        mask = df[target_col].notna()
        X = df.loc[mask, self._feature_cols].values
        y_raw = df.loc[mask, target_col].values
        y = self._le.transform(y_raw)
        return X, y

    def fit(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame,
        target_col: str = "ground_truth_label",
    ) -> "DecisionClassifier":
        self._feature_cols = [
            c for c in _decision_feature_cols(train_df)
            if train_df[c].notna().sum() > 5
        ]

        X_tr, y_tr = self._prepare(train_df, target_col)
        X_val, y_val = self._prepare(val_df, target_col)

        if len(X_tr) == 0:
            logger.error("No training rows for decision classifier.")
            return self

        X_tr = self._imputer.fit_transform(X_tr)
        X_val = self._imputer.transform(X_val) if len(X_val) > 0 else X_tr[:1]
        y_val_eval = y_val if len(y_val) > 0 else y_tr[:1]

        X_tr_s = self._scaler.fit_transform(X_tr)
        X_val_s = self._scaler.transform(X_val)

        best_f1 = -1.0
        for name, model in self._build_candidates().items():
            try:
                y_tr_fit, inv_map = (self._remap_labels(y_tr) if "xgboost" in name
                                     else (y_tr, None))
                model.fit(X_tr_s, y_tr_fit)
                raw_preds = model.predict(X_val_s)
                if "xgboost" in name and inv_map is not None:
                    preds = np.array([inv_map.get(int(p), int(p)) for p in raw_preds])
                else:
                    preds = raw_preds
                macro_f1 = f1_score(y_val_eval, preds, average="macro", zero_division=0)
                logger.info("  %s val macro-F1=%.3f", name, macro_f1)
                if macro_f1 > best_f1:
                    best_f1 = macro_f1
                    self._model = model
                    self._best_name = name
                    self._xgb_inv_map = inv_map if "xgboost" in name else None
            except Exception as exc:
                logger.warning("Candidate %s failed: %s", name, exc)

        if self._model is None:
            logger.error("All candidates failed.")
            return self

        preds_val = self._model.predict(X_val_s)
        proba_val = self._model.predict_proba(X_val_s)
        self.val_metrics = self._compute_metrics(y_val_eval, preds_val, proba_val)
        logger.info("Selected %s (val macro-F1=%.3f)", self._best_name, self.val_metrics["macro_f1"])
        return self

    def _compute_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_proba: np.ndarray,
    ) -> dict[str, Any]:
        classes = self._le.classes_
        n_classes = len(classes)
        labels = list(range(n_classes))

        report = classification_report(
            y_true, y_pred, labels=labels,
            target_names=classes, output_dict=True, zero_division=0,
        )
        cm = confusion_matrix(y_true, y_pred, labels=labels)

        pr_auc: dict[str, float] = {}
        for i, cls in enumerate(classes):
            binary = (y_true == i).astype(int)
            if binary.sum() > 0 and y_proba.shape[1] > i:
                prec, rec, _ = precision_recall_curve(binary, y_proba[:, i])
                pr_auc[cls] = float(auc(rec, prec))

        far: dict[str, float] = {}
        for i, cls in enumerate(classes):
            tp = cm[i, i]
            fp = int(cm[:, i].sum()) - tp
            fn = int(cm[i, :].sum()) - tp
            tn = int(cm.sum()) - tp - fp - fn
            far[cls] = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0

        return {
            "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
            "weighted_f1": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
            "per_class": report,
            "confusion_matrix": cm.tolist(),
            "pr_auc": pr_auc,
            "false_alarm_rate": far,
        }

    def _prepare_X(self, df: pd.DataFrame) -> np.ndarray:
        X = df[self._feature_cols].values
        X = self._imputer.transform(X)
        return self._scaler.transform(X)

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        if self._model is None:
            return np.full(len(df), "UNKNOWN", dtype=object)
        raw = self._model.predict(self._prepare_X(df))
        if getattr(self, "_xgb_inv_map", None) is not None:
            raw = np.array([self._xgb_inv_map.get(int(p), int(p)) for p in raw])
        return self._le.inverse_transform(raw.astype(int))

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        if self._model is None:
            n = len(self._le.classes_)
            return np.full((len(df), n), 1.0 / n)
        return self._model.predict_proba(self._prepare_X(df))

    @property
    def classes_(self) -> list[str]:
        return list(self._le.classes_)
