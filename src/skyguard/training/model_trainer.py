"""Multi-Model Training and Validation Engine for SkyGuard AI.

Fits all multi-model components:
- 6 Expected Value Regressors (Ridge, RF, ExtraTrees, XGBoost, GBR, HistGBR) per sensor
- 6 Anomaly Multi-Detector Ensemble (Isolation Forest, LOF, OCSVM, Elliptic, Mahalanobis, Robust Z)
- Statistical Quality Control Engine
- Fault Evidence Engine & Classifier
- Supervised Decision Classifier & Master Evidence Fusion
- Station Reliability Health Scores
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, f1_score

from skyguard.config.settings import settings
from skyguard.models.anomaly.detector import AnomalyDetector
from skyguard.models.decision.classifier import DecisionClassifier
from skyguard.models.expected.models import (
    ExpectedValueModel,
    apply_expected_models,
    fit_all_expected_models,
)
from skyguard.models.faults.classifier import FaultClassifier
from skyguard.models.faults.rules import apply_fault_rules
from skyguard.models.health.health_score import compute_health_scores
from skyguard.models.qc.statistical_qc import StatisticalQC

logger = logging.getLogger("skyguard.training.model_trainer")


class MultiModelTrainer:
    """Executes multi-model training, residual derivation, and validation metric assessment."""

    def __init__(self) -> None:
        self.qc_engine = StatisticalQC()

    def train_all_models(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame,
        progress_callback: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Train all model components and evaluate validation performance metrics."""
        np.random.seed(settings.random_seed)
        metrics: dict[str, Any] = {}

        # ── Step 1: Train Expected-Value Regression Ensembles ──────────────────
        if progress_callback:
            progress_callback(15.0, "TRAINING_EXPECTED_MODELS")
        logger.info("[ModelTrainer] Training Expected-Value Regressors for Temp, RH, Pressure...")

        expected_models = fit_all_expected_models(
            train_df=train_df,
            val_df=val_df,
            targets=["temperature_c", "relative_humidity_pct", "pressure_hpa"],
        )

        # Apply expected values and compute validation residuals
        train_df = apply_expected_models(train_df, expected_models)
        val_df = apply_expected_models(val_df, expected_models)

        expected_val_maes: dict[str, float] = {}
        for target, model in expected_models.items():
            val_mae = (
                model.summary_val_metrics.get("mae", 0.0)
                if hasattr(model, "summary_val_metrics") and isinstance(model.summary_val_metrics, dict)
                else 0.0
            )
            expected_val_maes[target] = round(float(val_mae), 3)
        metrics["expected_models_val_mae"] = expected_val_maes

        # ── Step 2: Statistical QC Assessment ─────────────────────────────────
        if progress_callback:
            progress_callback(35.0, "RUNNING_STATISTICAL_QC")
        logger.info("[ModelTrainer] Running Statistical QC Engine...")

        train_qc = [self.qc_engine.check_observation(row)["statistical_anomaly_score"] for _, row in train_df.iterrows()]
        val_qc = [self.qc_engine.check_observation(row)["statistical_anomaly_score"] for _, row in val_df.iterrows()]
        train_df["statistical_anomaly_score"] = train_qc
        val_df["statistical_anomaly_score"] = val_qc

        # ── Step 3: Train 6-Detector Anomaly Ensemble ─────────────────────────
        if progress_callback:
            progress_callback(50.0, "TRAINING_ANOMALY_ENSEMBLE")
        logger.info("[ModelTrainer] Training 6-Detector Anomaly Ensemble...")

        anomaly_detector = AnomalyDetector()
        anomaly_detector.fit(train_df)
        train_df = anomaly_detector.transform(train_df)
        val_df = anomaly_detector.transform(val_df)

        metrics["anomaly_detector_weights"] = anomaly_detector.weights

        # ── Step 4: Apply Fault Rules and Train Fault Classifier ───────────────
        if progress_callback:
            progress_callback(65.0, "TRAINING_FAULT_CLASSIFIER")
        logger.info("[ModelTrainer] Fitting Fault Classifier...")

        train_df = apply_fault_rules(train_df)
        val_df = apply_fault_rules(val_df)

        fault_clf = FaultClassifier()
        if "fault_description" in train_df.columns and train_df["fault_description"].notna().sum() > 5:
            fault_clf.fit(train_df)
        else:
            logger.info("[ModelTrainer] Limited fault labels in training data; using rule-based fault engine.")

        # ── Step 5: Train Supervised Decision Classifier (XGBoost) ─────────────
        if progress_callback:
            progress_callback(80.0, "TRAINING_DECISION_CLASSIFIER")
        logger.info("[ModelTrainer] Training Supervised Decision Classifier (XGBoost)...")

        train_df = self._ensure_target_labels(train_df)
        val_df = self._ensure_target_labels(val_df)

        decision_clf = DecisionClassifier()
        decision_clf.fit(train_df, val_df=val_df)

        # Evaluate on validation split
        y_val_true = val_df["ground_truth_label"].astype(str)
        val_preds = decision_clf.predict(val_df)
        macro_f1 = float(f1_score(y_val_true, val_preds, average="macro", zero_division=0))
        metrics["val_macro_f1"] = round(macro_f1, 4)

        try:
            report_dict = classification_report(y_val_true, val_preds, output_dict=True, zero_division=0)
            metrics["classification_report"] = report_dict
        except Exception:
            metrics["classification_report"] = {}

        # ── Step 6: Compute Station Health Scores ──────────────────────────────
        if progress_callback:
            progress_callback(92.0, "COMPUTING_STATION_HEALTH")
        logger.info("[ModelTrainer] Computing station health and reliability scores...")
        health_scores = compute_health_scores(train_df)

        if progress_callback:
            progress_callback(100.0, "EVALUATION_COMPLETE")

        logger.info(
            "[ModelTrainer] Training complete! Val Macro F1: %.4f | Temp MAE: %.2f | RH MAE: %.2f | MSLP MAE: %.2f",
            macro_f1,
            expected_val_maes.get("temperature_c", 0.0),
            expected_val_maes.get("relative_humidity_pct", 0.0),
            expected_val_maes.get("pressure_hpa", 0.0),
        )

        return {
            "expected_models": expected_models,
            "anomaly_detector": anomaly_detector,
            "fault_classifier": fault_clf,
            "decision_classifier": decision_clf,
            "health_scores": health_scores,
            "metrics": metrics,
        }

    @staticmethod
    def _ensure_target_labels(df: pd.DataFrame) -> pd.DataFrame:
        """Synthesize pseudo-labels if dataset lacks explicit ground truth columns."""
        if "ground_truth_label" in df.columns and df["ground_truth_label"].notna().sum() > 10:
            return df

        df = df.copy()
        labels = []
        for _, row in df.iterrows():
            is_freeze = bool(row.get("rule_freeze", False))
            is_spike = bool(row.get("rule_spike", False))
            is_drift = bool(row.get("rule_drift", False))
            is_comm = bool(row.get("rule_comm_failure", False))
            anom_score = float(row.get("combined_anomaly_score", 0.0))
            qc_score = float(row.get("statistical_anomaly_score", 0.0))

            if is_freeze or is_spike or is_drift or is_comm:
                labels.append("SENSOR_FAULT")
            elif anom_score > 0.65 and qc_score > 0.4:
                labels.append("SENSOR_FAULT")
            elif anom_score > 0.55:
                labels.append("GENUINE_EXTREME")
            else:
                labels.append("NORMAL")

        df["ground_truth_label"] = labels
        return df
