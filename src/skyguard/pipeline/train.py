"""Full Multi-Model Training Pipeline — run with: python scripts/train.py"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from skyguard.config.settings import settings
from skyguard.data.loader import load_raw
from skyguard.data.splitter import chronological_split
from skyguard.data.validator import validate
from skyguard.features.builder import FeatureBuilder
from skyguard.models.anomaly.detector import AnomalyDetector
from skyguard.models.decision.classifier import DecisionClassifier
from skyguard.models.events.weather_event import GenuineWeatherEventEngine
from skyguard.models.expected.models import (
    ExpectedValueModel,
    apply_expected_models,
    fit_all_expected_models,
)
from skyguard.models.faults.classifier import FaultClassifier
from skyguard.models.faults.engine import FaultEvidenceEngine
from skyguard.models.faults.rules import apply_fault_rules
from skyguard.models.fusion.master_fusion import MasterEvidenceFusion
from skyguard.models.health.health_score import compute_health_scores
from skyguard.models.qc.statistical_qc import StatisticalQC
from skyguard.preprocessing.pipeline import run_preprocessing, save_processed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("skyguard.train")


def _synthesize_silver_labels_if_needed(df: pd.DataFrame) -> pd.DataFrame:
    """Generate high-precision pseudo-labels if dataset lacks explicit ground truth columns."""
    if "ground_truth_label" in df.columns and df["ground_truth_label"].notna().sum() > 10:
        return df

    df = df.copy()
    labels = []
    fault_types = []

    for _, row in df.iterrows():
        is_freeze = bool(row.get("rule_freeze", False))
        is_spike = bool(row.get("rule_spike", False))
        is_drift = bool(row.get("rule_drift", False))
        is_comm = bool(row.get("rule_comm_failure", False))
        anom_score = float(row.get("combined_anomaly_score", 0.0))
        qc_score = float(row.get("statistical_anomaly_score", 0.0))
        spatial_agreement = float(row.get("neighbor_agreement_score", 1.0))

        is_extreme_wind = float(row.get("wind_speed_kmh", 0.0)) > 55.0
        is_extreme_rain = float(row.get("rainfall_mm", 0.0)) > 40.0

        if is_freeze or is_spike or is_drift or is_comm:
            labels.append("SENSOR_FAULT")
            if is_freeze:
                fault_types.append("FREEZE")
            elif is_spike:
                fault_types.append("SPIKE")
            elif is_drift:
                fault_types.append("DRIFT")
            else:
                fault_types.append("COMMUNICATION_FAILURE")
        elif (is_extreme_wind or is_extreme_rain or anom_score > 0.6) and (pd.isna(spatial_agreement) or spatial_agreement < 10.0):
            labels.append("GENUINE_EXTREME")
            fault_types.append("None")
        elif anom_score > 0.65 and qc_score > 0.4:
            labels.append("SENSOR_FAULT")
            fault_types.append("DRIFT")
        else:
            labels.append("NORMAL")
            fault_types.append("None")

    df["ground_truth_label"] = labels
    df["fault_description"] = fault_types
    return df


def main() -> None:
    logger.info("=== SkyGuard Multi-Model Intelligence Engine Training ===")
    seed = settings.random_seed
    np.random.seed(seed)

    # ── Step 1: Load & validate ──────────────────────────────────────────────
    df_raw = load_raw(settings.raw_data_path)
    report = validate(df_raw, settings.physical_bounds)
    if not report.is_valid:
        logger.error("Data validation failed: %s", report.missing_columns)
        sys.exit(1)

    # ── Step 2: Preprocessing ────────────────────────────────────────────────
    df_proc = run_preprocessing(df_raw)
    save_processed(df_proc, settings.processed_dir, "processed.parquet")

    # ── Step 3: Chronological split ──────────────────────────────────────────
    split_cfg = settings.data.get("split", {})
    data_split = chronological_split(
        df_proc,
        train_frac=split_cfg.get("train_frac", 0.60),
        val_frac=split_cfg.get("val_frac", 0.20),
    )
    train, val, test = data_split.train, data_split.val, data_split.test
    logger.info("Chronological Split — train=%d, val=%d, test=%d", len(train), len(val), len(test))

    # ── Step 4: Feature engineering (fit strictly on train only) ─────────────
    feat_cfg = settings.features
    builder = FeatureBuilder(
        lag_steps=feat_cfg.get("lag_steps", [1, 2, 3]),
        rolling_windows=feat_cfg.get("rolling_windows", [3, 6]),
        k_neighbors=feat_cfg.get("spatial_k_neighbors", 2),
    )
    train_feat = builder.fit_transform(train)
    val_feat = builder.transform(val)
    test_feat = builder.transform(test)

    # ── Step 5: Statistical Quality Control (QC) Engine ──────────────────────
    qc_engine = StatisticalQC()
    train_feat = qc_engine.transform(train_feat)
    val_feat = qc_engine.transform(val_feat)
    test_feat = qc_engine.transform(test_feat)

    # ── Step 6: Expected-Value Multi-Model Ensembles ──────────────────────────
    logger.info("Training candidate regression models and optimizing ensemble weights...")
    expected_models = fit_all_expected_models(train_feat, val_feat)
    train_feat = apply_expected_models(train_feat, expected_models)
    val_feat = apply_expected_models(val_feat, expected_models)
    test_feat = apply_expected_models(test_feat, expected_models)

    # ── Step 7: Unsupervised Anomaly Multi-Detector Ensemble ──────────────────
    logger.info("Fitting 6-detector unsupervised anomaly suite and calibrating normalization...")
    anomaly_detector = AnomalyDetector(random_state=seed)
    anomaly_detector.fit(train_feat)
    train_feat = anomaly_detector.transform(train_feat)
    val_feat = anomaly_detector.transform(val_feat)
    test_feat = anomaly_detector.transform(test_feat)

    # ── Step 8: Fault Rules & Fault Classifier ───────────────────────────────
    train_feat = apply_fault_rules(train_feat)
    val_feat = apply_fault_rules(val_feat)
    test_feat = apply_fault_rules(test_feat)

    train_feat = _synthesize_silver_labels_if_needed(train_feat)
    val_feat = _synthesize_silver_labels_if_needed(val_feat)
    test_feat = _synthesize_silver_labels_if_needed(test_feat)

    fault_clf = FaultClassifier()
    fault_clf.fit(train_feat, val_feat)

    # ── Step 9: Decision Classifier Benchmark ────────────────────────────────
    decision_clf = DecisionClassifier(random_state=seed)
    decision_clf.fit(train_feat, val_feat)

    # ── Step 10: Health Scores ───────────────────────────────────────────────
    full_feat = pd.concat([train_feat, val_feat, test_feat], ignore_index=True)
    health_scores = compute_health_scores(full_feat)

    # ── Step 11: Save Artifacts & Multi-Model Registry ───────────────────────
    _save_artifacts(
        builder, expected_models, anomaly_detector,
        decision_clf, fault_clf, health_scores,
        train_samples=len(train_feat),
        total_samples=len(df_raw),
        stations_count=int(df_raw["station_id"].nunique()),
        temporal_span_days=int((df_proc["timestamp"].max() - df_proc["timestamp"].min()).days) if "timestamp" in df_proc.columns else 7,
    )

    # ── Step 12: Final Test Set Evaluation ───────────────────────────────────
    _evaluate_test(decision_clf, test_feat)

    logger.info("=== Multi-Model Intelligence Engine Training Complete ===")


def _save_artifacts(
    builder, expected_models, anomaly_detector,
    decision_clf, fault_clf, health_scores,
    train_samples: int,
    total_samples: int = 50000,
    stations_count: int = 30,
    temporal_span_days: int = 70,
) -> None:
    art = settings.artifacts_dir

    # 1. Preprocessors
    (art / "preprocessors").mkdir(parents=True, exist_ok=True)
    joblib.dump(builder, art / "preprocessors" / "feature_builder.pkl")

    # 2. Expected Models
    (art / "models" / "expected").mkdir(parents=True, exist_ok=True)
    for target, model in expected_models.items():
        joblib.dump(model, art / "models" / "expected" / f"{target}.pkl")

    # 3. Anomaly Detectors
    (art / "models" / "anomaly").mkdir(parents=True, exist_ok=True)
    joblib.dump(anomaly_detector, art / "models" / "anomaly" / "detector.pkl")

    # 4. Decision Models
    (art / "models" / "decision").mkdir(parents=True, exist_ok=True)
    joblib.dump(decision_clf, art / "models" / "decision" / "classifier.pkl")

    # 5. Fault Models
    (art / "models" / "faults").mkdir(parents=True, exist_ok=True)
    joblib.dump(fault_clf, art / "models" / "faults" / "classifier.pkl")

    # 6. Health Models
    (art / "models" / "health").mkdir(parents=True, exist_ok=True)
    joblib.dump(health_scores, art / "models" / "health" / "health_scores.pkl")

    # 7. Model Registry & Comprehensive Metadata
    (art / "metadata").mkdir(parents=True, exist_ok=True)

    expected_metadata = {}
    for target, model in expected_models.items():
        expected_metadata[target] = {
            "target": target,
            "weights": getattr(model, "weights", {}),
            "summary_metrics": getattr(model, "summary_val_metrics", {}),
            "candidate_metrics": getattr(model, "val_metrics", {}),
            "best_single_model": getattr(model, "_best_name", ""),
        }

    registry = [
        # Expected value models
        {
            "name": "Temperature Regression Ensemble",
            "type": "expected_value_ensemble",
            "target": "temperature_c",
            "enabled": True,
            "status": "ACTIVE",
            "training_samples": train_samples,
            "candidates": ["ridge", "random_forest", "extra_trees", "xgboost", "gradient_boosting", "hist_gradient_boosting"],
            "weights": expected_models.get("temperature_c", ExpectedValueModel("temperature_c")).weights,
            "val_mae": expected_models.get("temperature_c", ExpectedValueModel("temperature_c")).summary_val_metrics.get("mae", 0.0),
            "val_rmse": expected_models.get("temperature_c", ExpectedValueModel("temperature_c")).summary_val_metrics.get("rmse", 0.0),
            "val_r2": expected_models.get("temperature_c", ExpectedValueModel("temperature_c")).summary_val_metrics.get("r2", 0.0),
            "purpose": "Predict expected temperature and calculate atmospheric residuals",
        },
        {
            "name": "Relative Humidity Regression Ensemble",
            "type": "expected_value_ensemble",
            "target": "relative_humidity_pct",
            "enabled": True,
            "status": "ACTIVE",
            "training_samples": train_samples,
            "candidates": ["ridge", "random_forest", "extra_trees", "xgboost", "gradient_boosting", "hist_gradient_boosting"],
            "weights": expected_models.get("relative_humidity_pct", ExpectedValueModel("relative_humidity_pct")).weights,
            "val_mae": expected_models.get("relative_humidity_pct", ExpectedValueModel("relative_humidity_pct")).summary_val_metrics.get("mae", 0.0),
            "val_rmse": expected_models.get("relative_humidity_pct", ExpectedValueModel("relative_humidity_pct")).summary_val_metrics.get("rmse", 0.0),
            "val_r2": expected_models.get("relative_humidity_pct", ExpectedValueModel("relative_humidity_pct")).summary_val_metrics.get("r2", 0.0),
            "purpose": "Predict expected relative humidity and calculate atmospheric residuals",
        },
        {
            "name": "Barometric Pressure Regression Ensemble",
            "type": "expected_value_ensemble",
            "target": "pressure_hpa",
            "enabled": True,
            "status": "ACTIVE",
            "training_samples": train_samples,
            "candidates": ["ridge", "random_forest", "extra_trees", "xgboost", "gradient_boosting", "hist_gradient_boosting"],
            "weights": expected_models.get("pressure_hpa", ExpectedValueModel("pressure_hpa")).weights,
            "val_mae": expected_models.get("pressure_hpa", ExpectedValueModel("pressure_hpa")).summary_val_metrics.get("mae", 0.0),
            "val_rmse": expected_models.get("pressure_hpa", ExpectedValueModel("pressure_hpa")).summary_val_metrics.get("rmse", 0.0),
            "val_r2": expected_models.get("pressure_hpa", ExpectedValueModel("pressure_hpa")).summary_val_metrics.get("r2", 0.0),
            "purpose": "Predict expected barometric pressure and detect pressure anomalies",
        },
        # Anomaly detectors
        {
            "name": "Isolation Forest",
            "type": "unsupervised_anomaly",
            "enabled": True,
            "status": "ACTIVE",
            "weight": 0.25,
            "training_samples": train_samples,
            "purpose": "Global outlier isolation through recursive random partitioning",
        },
        {
            "name": "Local Outlier Factor (LOF)",
            "type": "unsupervised_anomaly",
            "enabled": True,
            "status": "ACTIVE",
            "weight": 0.20,
            "training_samples": train_samples,
            "purpose": "Local density-based outlier detection for non-uniform clusters",
        },
        {
            "name": "One-Class SVM",
            "type": "unsupervised_anomaly",
            "enabled": True,
            "status": "ACTIVE",
            "weight": 0.20,
            "training_samples": train_samples,
            "purpose": "Nonlinear support vector boundary estimation for normal observations",
        },
        {
            "name": "Elliptic Envelope",
            "type": "unsupervised_anomaly",
            "enabled": True,
            "status": "ACTIVE",
            "weight": 0.15,
            "training_samples": train_samples,
            "purpose": "Fast Minimum Covariance Determinant (MCD) robust ellipsoid fitting",
        },
        {
            "name": "Mahalanobis Covariance Distance",
            "type": "multivariate_anomaly",
            "enabled": True,
            "status": "ACTIVE",
            "weight": 0.10,
            "training_samples": train_samples,
            "purpose": "Multivariate inter-sensor covariance distance measurement",
        },
        {
            "name": "Statistical Robust Z-Score",
            "type": "statistical_qc",
            "enabled": True,
            "status": "ACTIVE",
            "weight": 0.10,
            "training_samples": train_samples,
            "purpose": "Per-hour station median and MAD robust standardized deviations",
        },
        # Optional Deep Learning modules
        {
            "name": "Autoencoder Neural Detector",
            "type": "deep_learning_anomaly",
            "enabled": False,
            "status": "DISABLED",
            "weight": 0.0,
            "training_samples": 0,
            "purpose": "Non-linear bottleneck reconstruction (optional deep learning module)",
            "safety_note": "Multi-model tree and robust statistical ensemble prioritized for operational stability and explainability.",
        },
        {
            "name": "LSTM / GRU Temporal Sequence Model",
            "type": "deep_learning_temporal",
            "enabled": False,
            "status": "DISABLED",
            "weight": 0.0,
            "training_samples": 0,
            "purpose": "Recurrent sequence forecasting (optional deep learning module)",
            "safety_note": "Tree ensemble regression suite utilized for real-time inference efficiency.",
        },
        # Fault & Event Engines
        {
            "name": "Fault Evidence Engine",
            "type": "fault_diagnostics",
            "enabled": True,
            "status": "ACTIVE",
            "training_samples": train_samples,
            "purpose": "Heuristic and supervised diagnosis of DRIFT, FREEZE, SPIKE, and COMMUNICATION faults",
        },
        {
            "name": "Genuine Weather Event Engine",
            "type": "event_intelligence",
            "enabled": True,
            "status": "ACTIVE",
            "training_samples": train_samples,
            "purpose": "Multi-station spatial agreement and atmospheric front physical consistency",
        },
        {
            "name": "Master Evidence Fusion",
            "type": "decision_fusion",
            "enabled": True,
            "status": "ACTIVE",
            "training_samples": train_samples,
            "purpose": "Central multi-model consensus, uncertainty quantification, and decision classification",
        },
    ]

    metadata = {
        "model_version": f"v2.0-multimodel-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "train_date": datetime.now().isoformat(),
        "random_seed": settings.random_seed,
        "decision_model": decision_clf._best_name,
        "val_macro_f1": decision_clf.val_metrics.get("macro_f1", 0),
        "val_metrics": decision_clf.val_metrics,
        "expected_models": expected_metadata,
        "anomaly_detectors": anomaly_detector.get_detector_summary(),
        "model_registry": registry,
        "dataset_info": {
            "total_samples": total_samples,
            "train_samples": train_samples,
            "stations_count": stations_count,
            "temporal_span_days": temporal_span_days,
            "deep_learning_safely_disabled": True,
        },
    }

    with open(art / "metadata" / "model_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2, default=str)

    logger.info("All Multi-Model artifacts and metadata registered at %s", art)


def _evaluate_test(decision_clf: DecisionClassifier, test_feat: pd.DataFrame) -> None:
    from skyguard.evaluation.metrics import evaluate_classifier

    target_col = "ground_truth_label"
    if target_col not in test_feat.columns:
        logger.warning("No ground truth in test set; skipping evaluation.")
        return

    mask = test_feat[target_col].notna()
    if mask.sum() == 0:
        logger.warning("No test rows with ground truth labels.")
        return

    X_test = test_feat.loc[mask, decision_clf._feature_cols].values
    y_true_raw = test_feat.loc[mask, target_col].values
    y_true = decision_clf._le.transform(y_true_raw)

    X_test = decision_clf._imputer.transform(X_test)
    X_test_s = decision_clf._scaler.transform(X_test)
    y_pred = decision_clf._model.predict(X_test_s)
    y_proba = decision_clf._model.predict_proba(X_test_s)

    metrics = evaluate_classifier(y_true, y_pred, y_proba, decision_clf.classes_)

    logger.info("=== TEST SET EVALUATION ===")
    logger.info("Accuracy     : %.3f  (NOT primary metric)", metrics["accuracy"])
    logger.info("Macro F1     : %.3f", metrics["macro_f1"])
    logger.info("Weighted F1  : %.3f", metrics["weighted_f1"])
    for cls in decision_clf.classes_:
        r = metrics["per_class_report"].get(cls, {})
        logger.info(
            "  %-20s precision=%.3f recall=%.3f f1=%.3f support=%s",
            cls,
            r.get("precision", 0), r.get("recall", 0), r.get("f1-score", 0),
            r.get("support", 0),
        )

    reports_dir = settings.reports_dir / "metrics"
    reports_dir.mkdir(parents=True, exist_ok=True)
    with open(reports_dir / "test_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2, default=str)


if __name__ == "__main__":
    main()
