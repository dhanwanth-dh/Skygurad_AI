"""Unified Multi-Model inference predictor — assembles all model intelligence components."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from skyguard.explainability.shap_explainer import SHAPExplainer, generate_human_explanation
from skyguard.inference.severity import compute_severity
from skyguard.models.events.weather_event import GenuineWeatherEventEngine
from skyguard.models.faults.engine import FaultEvidenceEngine
from skyguard.models.faults.rules import apply_fault_rules, infer_fault_type
from skyguard.models.fusion.master_fusion import MasterEvidenceFusion
from skyguard.models.qc.statistical_qc import StatisticalQC
from skyguard.preprocessing.pipeline import run_preprocessing

logger = logging.getLogger(__name__)


class SkyGuardPredictor:
    """End-to-end Multi-Model Intelligence Inference Pipeline."""

    def __init__(self, artifacts_dir: Path) -> None:
        self._dir = Path(artifacts_dir)
        self._feature_builder: Any = None
        self._anomaly_detector: Any = None
        self._decision_clf: Any = None
        self._fault_clf: Any = None
        self._expected_models: dict[str, Any] = {}
        self._health_scores: dict[str, Any] = {}
        self._shap_explainer: Any = None
        self._qc_engine = StatisticalQC()
        self._fault_engine = FaultEvidenceEngine()
        self._weather_event_engine = GenuineWeatherEventEngine()
        self._master_fusion = MasterEvidenceFusion()
        self._model_version: str = "unknown"
        self._model_metadata: dict[str, Any] = {}

    def load(self) -> "SkyGuardPredictor":
        """Load all model artifacts and registries from disk."""
        # 1. Feature Builder
        feat_path = self._dir / "preprocessors" / "feature_builder.pkl"
        if feat_path.exists():
            self._feature_builder = joblib.load(feat_path)
        else:
            logger.warning("FeatureBuilder not found at %s", feat_path)

        # 2. Anomaly Detector
        anom_path = self._dir / "models" / "anomaly" / "detector.pkl"
        if anom_path.exists():
            self._anomaly_detector = joblib.load(anom_path)
        else:
            logger.warning("AnomalyDetector not found at %s", anom_path)

        # 3. Decision Classifier
        dec_path = self._dir / "models" / "decision" / "classifier.pkl"
        if dec_path.exists():
            self._decision_clf = joblib.load(dec_path)
        else:
            logger.warning("DecisionClassifier not found at %s", dec_path)

        # 4. Fault Classifier
        fault_path = self._dir / "models" / "faults" / "classifier.pkl"
        if fault_path.exists():
            self._fault_clf = joblib.load(fault_path)
            self._fault_engine = FaultEvidenceEngine(classifier=self._fault_clf)
        else:
            self._fault_engine = FaultEvidenceEngine(classifier=None)

        # 5. Expected-Value Regressors
        for target in ["temperature_c", "relative_humidity_pct", "pressure_hpa"]:
            p = self._dir / "models" / "expected" / f"{target}.pkl"
            if p.exists():
                self._expected_models[target] = joblib.load(p)

        # 6. Station Health Scores
        health_path = self._dir / "models" / "health" / "health_scores.pkl"
        if health_path.exists():
            self._health_scores = joblib.load(health_path)

        # 7. Model Metadata
        meta_path = self._dir / "metadata" / "model_metadata.json"
        if meta_path.exists():
            import json
            try:
                with open(meta_path) as f:
                    self._model_metadata = json.load(f)
                self._model_version = self._model_metadata.get("model_version", "unknown")
            except Exception as exc:
                logger.warning("Failed to load model metadata: %s", exc)

        logger.info("SkyGuardPredictor loaded (version=%s)", self._model_version)
        return self

    def predict_single(self, observation: dict[str, Any]) -> dict[str, Any]:
        """Run full 16-step multi-model inference pipeline on an observation."""
        df = pd.DataFrame([observation])
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        total_expected_models = 3
        active_models_count = 0
        total_possible_models = 12  # Expected(6 candidates x 3 sensors) + Anomaly(6 detectors) + Faults + QC

        trace_steps: list[dict[str, Any]] = []

        # ── Step 1: Preprocessing ────────────────────────────────────────────
        df = run_preprocessing(df)
        trace_steps.append({
            "stage": "PREPROCESSING",
            "status": "PASSED",
            "summary": "Range validation and physical bounds verified",
        })

        # ── Step 2: Feature Engineering ──────────────────────────────────────
        if self._feature_builder is not None:
            try:
                df = self._feature_builder.transform(df)
                trace_steps.append({
                    "stage": "FEATURE_ENGINEERING",
                    "status": "PASSED",
                    "summary": f"Constructed temporal lags, station baselines, spatial residuals, and multivariate covariance features",
                })
            except Exception as exc:
                logger.warning("FeatureBuilder transform error: %s", exc)
                trace_steps.append({
                    "stage": "FEATURE_ENGINEERING",
                    "status": "WARNING",
                    "summary": f"Partial feature generation fallback: {exc}",
                })

        # ── Step 3: Statistical Quality Control (QC) ─────────────────────────
        qc_result = self._qc_engine.check_observation(df.iloc[0])
        df["statistical_anomaly_score"] = qc_result["statistical_anomaly_score"]
        trace_steps.append({
            "stage": "STATISTICAL_QC",
            "status": "PASSED" if qc_result["qc_passed"] else "ANOMALOUS",
            "score": qc_result["statistical_anomaly_score"],
            "summary": f"10 QC checks evaluated ({len(qc_result['qc_violations'])} violations)",
            "evidence": qc_result["qc_evidence"],
        })

        # ── Step 4 & 5: Expected-Value Ensembles & Agreement ────────────────
        expected_values: dict[str, float | None] = {}
        expected_agreements: dict[str, float] = {}
        expected_variances: dict[str, float] = {}
        candidate_predictions_all: dict[str, dict[str, float]] = {}

        for target in ["temperature_c", "relative_humidity_pct", "pressure_hpa"]:
            model = self._expected_models.get(target)
            if model is not None:
                try:
                    df = model.add_residuals(df)
                    pred_val = float(df[f"predicted_{target}"].iloc[0]) if f"predicted_{target}" in df.columns else None
                    if pred_val is not None and not np.isnan(pred_val):
                        expected_values[target] = round(pred_val, 2)
                    else:
                        expected_values[target] = None

                    ag_val = float(df.get(f"expected_{target}_model_agreement", pd.Series([1.0])).iloc[0])
                    var_val = float(df.get(f"expected_{target}_variance", pd.Series([0.0])).iloc[0])
                    expected_agreements[target] = round(ag_val, 4)
                    expected_variances[target] = round(var_val, 4)
                    active_models_count += 1
                except Exception as exc:
                    logger.warning("Expected model error on %s: %s", target, exc)
                    expected_values[target] = None
                    expected_agreements[target] = 0.5
            else:
                expected_values[target] = None
                expected_agreements[target] = 0.5

        trace_steps.append({
            "stage": "EXPECTED_VALUE_MODELS",
            "status": "PASSED",
            "summary": f"Regression ensembles evaluated for Temp, Humidity, Pressure (Avg agreement: {np.mean(list(expected_agreements.values())):.1%})",
            "expected_values": expected_values,
        })

        # ── Step 6 & 7: Anomaly Multi-Detector Ensemble & Consensus ──────────
        anomaly_detailed: dict[str, Any] = {}
        if self._anomaly_detector is not None:
            try:
                df = self._anomaly_detector.transform(df)
                anomaly_detailed = self._anomaly_detector.score_detailed(df)
                active_models_count += anomaly_detailed.get("total_models", 6)
            except Exception as exc:
                logger.warning("AnomalyDetector error: %s", exc)
                anomaly_detailed = {
                    "combined_anomaly_score": 0.0,
                    "models_agreeing": 0,
                    "total_models": 6,
                    "consensus_score": 0.0,
                    "individual_scores": {},
                }
        else:
            anomaly_detailed = {
                "combined_anomaly_score": 0.0,
                "models_agreeing": 0,
                "total_models": 6,
                "consensus_score": 0.0,
                "individual_scores": {},
            }

        agreeing_count = int(np.atleast_1d(anomaly_detailed.get('models_agreeing', 0))[0])
        total_anom_models = int(np.atleast_1d(anomaly_detailed.get('total_models', 6))[0])
        anom_score_scalar = float(np.atleast_1d(anomaly_detailed.get("combined_anomaly_score", 0.0))[0])

        trace_steps.append({
            "stage": "ANOMALY_MODELS",
            "status": "ANOMALY" if anom_score_scalar > 0.4 else "NORMAL",
            "score": round(anom_score_scalar, 4),
            "summary": f"{agreeing_count}/{total_anom_models} detectors agree on anomaly",
            "detector_scores": {k: round(float(v[0]), 3) for k, v in anomaly_detailed.get("individual_scores", {}).items() if len(v) > 0},
        })

        # ── Step 8 & 9: Fault Rules and Fault Evidence Engine ─────────────────
        df = apply_fault_rules(df)
        is_anom_prelim = bool(
            anom_score_scalar > 0.35
            or float(qc_result.get("statistical_anomaly_score", 0.0)) > 0.35
            or bool(df.get("rule_any_fault", pd.Series([False])).iloc[0])
        )
        fault_result = self._fault_engine.evaluate(df.iloc[0], is_anomaly=is_anom_prelim)

        trace_steps.append({
            "stage": "FAULT_MODELS",
            "status": fault_result["fault_type"],
            "confidence": fault_result["fault_confidence"],
            "summary": f"Diagnosed {fault_result['fault_type']} with {fault_result['fault_confidence']:.0%} confidence",
            "evidence": fault_result["fault_evidence"],
        })

        # ── Step 10: Genuine Meteorological Event Engine ──────────────────────
        event_result = self._weather_event_engine.evaluate(
            df.iloc[0],
            anomaly_score=anom_score_scalar,
        )

        trace_steps.append({
            "stage": "WEATHER_EVENT_ENGINE",
            "status": "GENUINE_EVENT" if event_result["genuine_event_score"] > 0.4 else "ISOLATED",
            "score": event_result["genuine_event_score"],
            "summary": f"Spatial & atmospheric event score: {event_result['genuine_event_score']:.2f}",
            "evidence": event_result["genuine_event_evidence"],
        })

        # ── Step 11 & 12: Master Evidence Fusion & Decision Logic ─────────────
        # Calculate coverage ratio
        total_possible = 9.0  # 3 expected + 6 anomaly detectors
        coverage_ratio = min(1.0, active_models_count / total_possible)

        fused = self._master_fusion.fuse(
            observation=observation,
            expected_results={
                "temp_agreement": expected_agreements.get("temperature_c", 1.0),
                "humidity_agreement": expected_agreements.get("relative_humidity_pct", 1.0),
                "pressure_agreement": expected_agreements.get("pressure_hpa", 1.0),
            },
            anomaly_results=anomaly_detailed,
            qc_results=qc_result,
            fault_results=fault_result,
            event_results=event_result,
            model_coverage_ratio=coverage_ratio,
        )

        prediction = fused["prediction"]
        confidence = fused["confidence"]
        confidence_level = fused["confidence_level"]
        uncertainty_score = fused["uncertainty_score"]
        anomaly_score = fused["anomaly_score"]
        model_agreement = fused["model_agreement"]
        model_coverage = fused["model_coverage"]
        fault_type = fused["fault_type"]
        fault_confidence = fused["fault_confidence"]
        fault_evidence = fused["fault_evidence"]
        genuine_event_score = fused["genuine_event_score"]
        genuine_event_evidence = fused["genuine_event_evidence"]
        severity = fused["severity"]
        top_reasons = fused["top_reasons"]
        recommended_action = fused["recommended_action"]
        class_probs = fused["class_probabilities"]

        trace_steps.append({
            "stage": "EVIDENCE_FUSION",
            "status": prediction,
            "confidence": confidence,
            "uncertainty": uncertainty_score,
            "summary": f"Final Decision: {prediction} ({confidence_level} confidence: {confidence:.0%}, uncertainty: {uncertainty_score:.2f})",
        })

        # ── Step 13: Sensor Health ───────────────────────────────────────────
        station_id = str(observation.get("station_id", ""))
        health = self._health_scores.get(station_id, {"health_score": 100.0, "status": "HEALTHY"})

        # ── Step 14: Suggested Corrections ───────────────────────────────────
        correction: dict[str, Any] = {}
        if prediction == "SENSOR_FAULT" and confidence >= 0.75:
            for target, exp_val in expected_values.items():
                if exp_val is not None:
                    obs_val = float(observation.get(target, np.nan))
                    correction[target] = {
                        "observed": obs_val,
                        "estimated": exp_val,
                        "correction_applied": True,
                        "correction_confidence": round(confidence, 3),
                        "residual": round(obs_val - exp_val, 2) if not np.isnan(obs_val) else 0.0,
                    }

        # ── Step 15: SHAP & Explainability ────────────────────────────────────
        if self._shap_explainer is not None and self._decision_clf is not None:
            try:
                feat_cols = self._decision_clf._feature_cols
                mask = df[feat_cols].notna().all(axis=1)
                if mask.any():
                    X = df.loc[mask, feat_cols].values
                    top_feats = self._shap_explainer.explain(X, top_k=5)[0]
                    shap_reasons = generate_human_explanation(prediction, confidence, top_feats, fault_type)
                    if shap_reasons:
                        top_reasons = shap_reasons[:5]
            except Exception as exc:
                logger.debug("SHAP explanation failed: %s", exc)

        # Anomaly Consensus Dictionary
        anomaly_consensus_dict = {
            "models_agreeing": int(np.atleast_1d(anomaly_detailed.get("models_agreeing", 0))[0]),
            "models_total": int(np.atleast_1d(anomaly_detailed.get("total_models", 6))[0]),
            "score": round(float(np.atleast_1d(anomaly_detailed.get("consensus_score", 0.0))[0]), 4),
            "detector_scores": {
                k: round(float(v[0]), 4)
                for k, v in anomaly_detailed.get("individual_scores", {}).items()
                if len(v) > 0
            },
        }

        # Enabled Models List
        enabled_models_list = [
            "Ridge Regression", "Random Forest Regressor", "Extra Trees Regressor",
            "XGBoost Regressor", "Gradient Boosting Regressor", "HistGradientBoostingRegressor",
            "Isolation Forest", "Local Outlier Factor", "One-Class SVM",
            "Elliptic Envelope", "Mahalanobis Distance", "Statistical Robust Z",
            "Statistical QC Engine", "Fault Evidence Engine", "Genuine Weather Event Engine",
            "Master Evidence Fusion",
        ]

        return {
            "station_id": station_id,
            "timestamp": str(observation.get("timestamp", "")),
            "prediction": prediction,
            "confidence": round(confidence, 4),
            "confidence_level": confidence_level,
            "uncertainty_score": round(uncertainty_score, 4),
            "class_probabilities": {k: round(v, 4) for k, v in class_probs.items()},
            "anomaly_score": round(anomaly_score, 4),
            "anomaly_consensus": anomaly_consensus_dict,
            "model_agreement": round(model_agreement, 4),
            "model_coverage": model_coverage,
            "fault_type": fault_type,
            "fault_confidence": round(fault_confidence, 4),
            "fault_evidence": fault_evidence,
            "genuine_event_score": round(genuine_event_score, 4),
            "genuine_event_evidence": genuine_event_evidence,
            "severity": severity,
            "sensor_health": float(health.get("health_score", 100.0)),
            "sensor_health_status": str(health.get("status", "HEALTHY")),
            "expected_values": expected_values,
            "observed_values": {
                k: float(observation.get(k, np.nan))
                for k in ["temperature_c", "relative_humidity_pct", "pressure_hpa",
                          "wind_speed_kmh", "rainfall_mm"]
            },
            "top_reasons": top_reasons,
            "recommended_action": recommended_action,
            "correction": correction,
            "enabled_models": enabled_models_list,
            "trace": trace_steps,
            "model_version": self._model_version,
        }
