"""Tests for fault rules and health score."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from skyguard.config.settings import settings
from skyguard.data.loader import load_raw
from skyguard.models.faults.rules import detect_freeze, detect_spike, detect_drift
from skyguard.models.health.health_score import compute_health_scores
from skyguard.preprocessing.pipeline import run_preprocessing
from skyguard.inference.severity import compute_severity


@pytest.fixture(scope="module")
def sample_df():
    df = load_raw(settings.raw_data_path)
    return run_preprocessing(df.iloc[:1000])


def test_freeze_detection():
    df = pd.DataFrame({
        "station_id": ["AWS_01"] * 10,
        "timestamp": pd.date_range("2025-01-01", periods=10, freq="1h"),
        "relative_humidity_pct": [50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0],
    })
    flags = detect_freeze(df, col="relative_humidity_pct", variance_threshold=0.01, min_consecutive=3)
    assert flags.sum() >= 5


def test_spike_detection():
    df = pd.DataFrame({
        "station_id": ["AWS_01"] * 10,
        "timestamp": pd.date_range("2025-01-01", periods=10, freq="1h"),
        "pressure_hpa": [1010.0, 1010.0, 1010.0, 1010.0, 850.0, 1010.0, 1010.0, 1010.0, 1010.0, 1010.0],
    })
    flags = detect_spike(df, col="pressure_hpa", zscore_threshold=2.0)
    assert flags.iloc[4], "Spike not detected"


def test_health_score_range(sample_df):
    scores = compute_health_scores(sample_df)
    for station, info in scores.items():
        assert 0 <= info["health_score"] <= 100
        assert info["status"] in ("HEALTHY", "NEEDS_ATTENTION", "DEGRADED", "CRITICAL")


def test_health_score_faulty_station_lower():
    df = pd.DataFrame({
        "station_id": ["AWS_HEALTHY"] * 10 + ["AWS_FAULTY"] * 10,
        "timestamp": list(pd.date_range("2025-01-01", periods=10, freq="1h")) * 2,
        "ground_truth_label": ["NORMAL"] * 10 + ["SENSOR_FAULT"] * 8 + ["NORMAL"] * 2,
    })
    scores = compute_health_scores(df)
    assert scores["AWS_FAULTY"]["health_score"] < scores["AWS_HEALTHY"]["health_score"]


def test_severity_normal_is_low():
    assert compute_severity("NORMAL", 0.99, 0.9) == "LOW"


def test_severity_fault_critical():
    assert compute_severity("SENSOR_FAULT", 0.95, 0.9, "DRIFT") == "CRITICAL"


def test_severity_extreme_high():
    assert compute_severity("GENUINE_EXTREME", 0.85, 0.7) == "HIGH"
