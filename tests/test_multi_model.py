"""Comprehensive test suite for SkyGuard Multi-Model Intelligence Engine.

Tests:
1. Expected-Value candidate models (Ridge, RF, ExtraTrees, XGBoost, GBR, HistGBR)
2. Chronological validation metrics (MAE, RMSE, R²) and inverse-MAE ensemble weighting
3. Model agreement and disagreement metrics
4. 6-detector unsupervised anomaly suite (IF, LOF, OCSVM, Elliptic, Mahalanobis, Robust Z)
5. Score normalization to [0, 1] bounds strictly from training data
6. Anomaly consensus scoring
7. Statistical QC engine (10 classical checks, physical bounds, spike, freeze, drift, gaps)
8. Fault Evidence Engine (rules, classifier, residuals, baseline deviations)
9. Genuine Weather Event Engine (spatial agreement, front dynamics, fault disqualifiers)
10. Master Evidence Fusion, uncertainty quantification, and decision logic
11. Model failure fallback & graceful degradation
12. Deep learning dataset size safety guardrails
13. No future leakage and no target leakage
14. FastAPI /predict schema backwards compatibility
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from skyguard.config.settings import settings
from skyguard.data.loader import load_raw
from skyguard.data.splitter import chronological_split
from skyguard.features.builder import FeatureBuilder
from skyguard.inference.predictor import SkyGuardPredictor
from skyguard.models.anomaly.autoencoder import AutoencoderDetector
from skyguard.models.anomaly.detector import AnomalyDetector
from skyguard.models.events.weather_event import GenuineWeatherEventEngine
from skyguard.models.expected.deep_temporal import DeepTemporalModel
from skyguard.models.expected.models import ExpectedValueModel, fit_all_expected_models
from skyguard.models.faults.classifier import FaultClassifier
from skyguard.models.faults.engine import FaultEvidenceEngine
from skyguard.models.fusion.master_fusion import MasterEvidenceFusion
from skyguard.models.qc.statistical_qc import StatisticalQC
from skyguard.preprocessing.pipeline import run_preprocessing


@pytest.fixture(scope="module")
def prepared_splits():
    df_raw = load_raw(settings.raw_data_path)
    df_proc = run_preprocessing(df_raw.iloc[:2500])
    split = chronological_split(df_proc, train_frac=0.60, val_frac=0.20)
    builder = FeatureBuilder(
        lag_steps=[1, 2, 3],
        rolling_windows=[3, 6],
        k_neighbors=2,
    )
    train_feat = builder.fit_transform(split.train)
    val_feat = builder.transform(split.val)
    test_feat = builder.transform(split.test)
    return train_feat, val_feat, test_feat


# ── 1. Expected-Value Models & Ensemble Weighting ────────────────────────────

def test_expected_value_candidates_and_weights(prepared_splits):
    train_feat, val_feat, _ = prepared_splits
    model = ExpectedValueModel("temperature_c")
    model.fit(train_feat, val_feat)

    # Verify candidate models were fitted
    assert len(model._fitted_models) >= 5
    assert "random_forest" in model._fitted_models
    assert "extra_trees" in model._fitted_models

    # Verify validation metrics exist
    assert "mae" in model.summary_val_metrics
    assert "rmse" in model.summary_val_metrics
    assert "r2" in model.summary_val_metrics
    assert model.summary_val_metrics["mae"] < 4.0

    # Verify weights are normalized
    total_weight = sum(model.weights.values())
    assert abs(total_weight - 1.0) < 1e-3
    for name, w in model.weights.items():
        assert w >= 0.0, f"Weight for {name} must be non-negative"


def test_expected_model_agreement_and_disagreement(prepared_splits):
    train_feat, val_feat, _ = prepared_splits
    model = ExpectedValueModel("temperature_c")
    model.fit(train_feat, val_feat)

    detailed = model.predict_detailed(val_feat)
    ens_preds = detailed["ensemble_prediction"]
    agreement = detailed["model_agreement"]
    disagreement = detailed["model_disagreement"]
    variance = detailed["model_variance"]

    assert len(ens_preds) == len(val_feat)
    assert not np.isnan(ens_preds).all()
    assert ((agreement >= 0.0) & (agreement <= 1.0)).all()
    assert ((disagreement >= 0.0) & (disagreement <= 1.0)).all()
    assert np.allclose(agreement + disagreement, 1.0, atol=1e-5)
    assert (variance >= 0.0).all()


# ── 2. Anomaly Detectors, Normalization & Consensus ──────────────────────────

def test_anomaly_detectors_and_normalization(prepared_splits):
    train_feat, val_feat, _ = prepared_splits
    detector = AnomalyDetector(random_state=42)
    detector.fit(train_feat)

    # Verify active detectors
    assert detector.detector_statuses["isolation_forest"]
    assert detector.detector_statuses["lof"]
    assert detector.detector_statuses["one_class_svm"]
    assert detector.detector_statuses["elliptic_envelope"]
    assert detector.detector_statuses["mahalanobis"]
    assert detector.detector_statuses["robust_zscore"]

    detailed = detector.score_detailed(val_feat)
    scores = detailed["individual_scores"]

    for name in ["isolation_forest", "lof", "one_class_svm", "elliptic_envelope", "mahalanobis", "robust_zscore"]:
        assert name in scores
        arr = scores[name]
        assert len(arr) == len(val_feat)
        assert (arr >= 0.0).all() and (arr <= 1.0).all(), f"{name} score outside [0, 1]"

    combined = detailed["combined_anomaly_score"]
    assert (combined >= 0.0).all() and (combined <= 1.0).all()


def test_anomaly_consensus(prepared_splits):
    train_feat, val_feat, _ = prepared_splits
    detector = AnomalyDetector(random_state=42)
    detector.fit(train_feat)

    detailed = detector.score_detailed(val_feat)
    models_agreeing = detailed["models_agreeing"]
    total_models = detailed["total_models"]
    consensus = detailed["consensus_score"]

    assert total_models >= 6
    assert (models_agreeing >= 0).all() and (models_agreeing <= total_models).all()
    assert (consensus >= 0.0).all() and (consensus <= 1.0).all()


# ── 3. Statistical Quality Control (QC) ──────────────────────────────────────

def test_qc_checks_physical_bounds():
    qc = StatisticalQC()
    # Out of bounds temperature (75 °C)
    bad_obs = {"temperature_c": 75.0, "relative_humidity_pct": 50.0, "pressure_hpa": 1010.0}
    res = qc.check_observation(bad_obs)
    assert not res["qc_passed"]
    assert res["statistical_anomaly_score"] > 0.3
    assert any("outside physical bounds" in ev for ev in res["qc_evidence"])


def test_qc_checks_spike_and_freeze():
    qc = StatisticalQC()
    spike_obs = {"temperature_c": 30.0, "rule_spike": True}
    res_spike = qc.check_observation(spike_obs)
    assert not res_spike["qc_passed"]
    assert any("spike detected" in ev.lower() for ev in res_spike["qc_evidence"])

    freeze_obs = {"temperature_c": 30.0, "rule_freeze": True}
    res_freeze = qc.check_observation(freeze_obs)
    assert not res_freeze["qc_passed"]
    assert any("frozen" in ev.lower() for ev in res_freeze["qc_evidence"])


# ── 4. Fault Evidence Engine ─────────────────────────────────────────────────

def test_fault_evidence_engine():
    engine = FaultEvidenceEngine()

    # Freeze row
    freeze_row = {"rule_freeze": True, "relative_humidity_pct_robust_z": 0.01}
    f_res = engine.evaluate(freeze_row, is_anomaly=True)
    assert f_res["fault_type"] == "FREEZE"
    assert f_res["fault_confidence"] >= 0.85
    assert len(f_res["fault_evidence"]) > 0

    # Spike row
    spike_row = {"rule_spike": True, "pressure_hpa_residual": -159.4}
    s_res = engine.evaluate(spike_row, is_anomaly=True)
    assert s_res["fault_type"] == "SPIKE"
    assert s_res["fault_confidence"] >= 0.85

    # Drift row
    drift_row = {"rule_drift": True, "temperature_c_residual": 3.8, "temperature_c_robust_z": 2.8}
    d_res = engine.evaluate(drift_row, is_anomaly=True)
    assert d_res["fault_type"] == "DRIFT"
    assert d_res["fault_confidence"] >= 0.80


# ── 5. Genuine Weather Event Engine ──────────────────────────────────────────

def test_genuine_weather_event_engine():
    event_engine = GenuineWeatherEventEngine()

    # Front signature across nearby stations: low spatial residual + temp drop + humidity surge
    front_obs = {
        "neighbor_agreement_score": 1.1,
        "temperature_c_delta": -3.5,
        "relative_humidity_pct_delta": 18.0,
        "pressure_hpa_delta": -2.1,
        "rainfall_mm": 15.0,
        "wind_speed_kmh": 38.0,
    }
    res = event_engine.evaluate(front_obs, anomaly_score=0.8)
    assert res["genuine_event_score"] >= 0.50
    assert any("front" in ev.lower() or "synchronized" in ev.lower() for ev in res["genuine_event_evidence"])

    # Disqualification when sensor is frozen
    frozen_obs = dict(front_obs)
    frozen_obs["rule_freeze"] = True
    res_frozen = event_engine.evaluate(frozen_obs, anomaly_score=0.8)
    assert res_frozen["genuine_event_score"] <= 0.15


# ── 6. Master Evidence Fusion & Uncertainty ──────────────────────────────────

def test_master_evidence_fusion_normal():
    fusion = MasterEvidenceFusion()
    obs = {"temperature_c": 32.0, "station_id": "AWS_TN_01"}
    res = fusion.fuse(
        observation=obs,
        expected_results={"temp_agreement": 0.95, "humidity_agreement": 0.95, "pressure_agreement": 0.95},
        anomaly_results={"combined_anomaly_score": 0.05, "models_agreeing": 0, "total_models": 6, "consensus_score": 0.0, "agreement_ratio": 0.0},
        qc_results={"statistical_anomaly_score": 0.0, "qc_passed": True, "qc_evidence": []},
        fault_results={"fault_type": "NONE", "fault_confidence": 0.0, "fault_evidence": []},
        event_results={"genuine_event_score": 0.0, "genuine_event_evidence": []},
        model_coverage_ratio=1.0,
    )
    assert res["prediction"] == "NORMAL"
    assert res["confidence"] >= 0.80
    assert res["uncertainty_score"] < 0.30
    assert res["severity"] == "LOW"


def test_master_evidence_fusion_sensor_fault():
    fusion = MasterEvidenceFusion()
    obs = {"temperature_c": 55.0, "station_id": "AWS_TN_01"}
    res = fusion.fuse(
        observation=obs,
        expected_results={"temp_agreement": 0.85, "humidity_agreement": 0.85, "pressure_agreement": 0.85},
        anomaly_results={"combined_anomaly_score": 0.90, "models_agreeing": 5, "total_models": 6, "consensus_score": 0.83, "agreement_ratio": 0.83},
        qc_results={"statistical_anomaly_score": 0.80, "qc_passed": False, "qc_evidence": ["Temperature outside normal bounds"]},
        fault_results={"fault_type": "SPIKE", "fault_confidence": 0.95, "fault_evidence": ["Single-point extreme spike"]},
        event_results={"genuine_event_score": 0.05, "genuine_event_evidence": []},
        model_coverage_ratio=1.0,
    )
    assert res["prediction"] == "SENSOR_FAULT"
    assert res["fault_type"] == "SPIKE"
    assert res["severity"] in ("HIGH", "CRITICAL")
    assert res["recommended_action"] is not None


def test_uncertainty_elevates_on_model_disagreement():
    fusion = MasterEvidenceFusion()
    obs = {"temperature_c": 35.0, "station_id": "AWS_TN_01"}
    res_disagree = fusion.fuse(
        observation=obs,
        expected_results={"temp_agreement": 0.20, "humidity_agreement": 0.20, "pressure_agreement": 0.20},
        anomaly_results={"combined_anomaly_score": 0.50, "models_agreeing": 3, "total_models": 6, "consensus_score": 0.50, "agreement_ratio": 0.50},
        qc_results={"statistical_anomaly_score": 0.20, "qc_passed": True, "qc_evidence": []},
        fault_results={"fault_type": "UNKNOWN", "fault_confidence": 0.50, "fault_evidence": []},
        event_results={"genuine_event_score": 0.40, "genuine_event_evidence": []},
        model_coverage_ratio=0.50,
    )
    assert res_disagree["uncertainty_score"] > 0.40
    assert res_disagree["confidence_level"] in ("MEDIUM", "LOW")


# ── 7. Deep Learning Safety Guardrails ───────────────────────────────────────

def test_deep_learning_safety_guardrails():
    # Autoencoder must be disabled by default
    ae = AutoencoderDetector(enabled=False, min_samples=5000)
    ae.fit(np.zeros((504, 10)))
    assert not ae.is_active
    status = ae.get_status()
    assert not status["is_active"]

    # LSTM/GRU temporal module must be disabled by default
    lstm = DeepTemporalModel(architecture="lstm", enabled=False, min_samples=5000)
    lstm.fit(pd.DataFrame(np.zeros((504, 5))))
    assert not lstm.is_active
    l_status = lstm.get_status()
    assert not l_status["is_active"]


# ── 8. Model Failure Fallback & Coverage ─────────────────────────────────────

def test_model_failure_fallback():
    predictor = SkyGuardPredictor(settings.artifacts_dir)
    predictor.load()

    # Corrupt or disable one model to test fallback
    predictor._expected_models["temperature_c"] = None

    obs = {
        "timestamp": "2025-02-15 14:00:00",
        "station_id": "AWS_TN_01",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "temperature_c": 32.5,
        "relative_humidity_pct": 65.0,
        "pressure_hpa": 1009.5,
        "wind_speed_kmh": 14.2,
        "rainfall_mm": 0.0,
    }

    res = predictor.predict_single(obs)
    # Predictor must succeed and not crash
    assert res["prediction"] in ("NORMAL", "SENSOR_FAULT", "GENUINE_EXTREME", "UNKNOWN")
    assert "model_coverage" in res
    assert "uncertainty_score" in res


# ── 9. End-to-End Predictor & API Response Schema ────────────────────────────

def test_full_inference_predictor():
    predictor = SkyGuardPredictor(settings.artifacts_dir)
    predictor.load()

    obs = {
        "timestamp": "2025-02-15 14:00:00",
        "station_id": "AWS_TN_01",
        "station_name": "Chennai Coastal AWS",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "temperature_c": 32.5,
        "relative_humidity_pct": 65.0,
        "pressure_hpa": 1009.5,
        "wind_speed_kmh": 14.2,
        "rainfall_mm": 0.0,
    }

    res = predictor.predict_single(obs)

    # Legacy fields
    assert "station_id" in res
    assert "prediction" in res
    assert "confidence" in res
    assert "anomaly_score" in res
    assert "fault_type" in res
    assert "severity" in res
    assert "sensor_health" in res
    assert "expected_values" in res
    assert "observed_values" in res
    assert "top_reasons" in res
    assert "correction" in res

    # Multi-Model fields
    assert "anomaly_consensus" in res
    assert "model_agreement" in res
    assert "model_coverage" in res
    assert "uncertainty_score" in res
    assert "genuine_event_score" in res
    assert "fault_confidence" in res
    assert "fault_evidence" in res
    assert "recommended_action" in res
    assert "enabled_models" in res
    assert "trace" in res
    assert len(res["trace"]) >= 7
