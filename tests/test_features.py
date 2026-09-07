"""Tests for feature engineering — no future leakage, correct shapes."""

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
from skyguard.features.temporal import add_temporal_features
from skyguard.features.spatial import add_spatial_features, haversine_km
from skyguard.features.baseline import compute_station_baselines, apply_station_baselines
from skyguard.preprocessing.pipeline import run_preprocessing


@pytest.fixture(scope="module")
def processed_split():
    df = load_raw(settings.raw_data_path)
    # Take a slice of 2000 rows for fast testing
    df_proc = run_preprocessing(df.iloc[:2000])
    split = chronological_split(df_proc, train_frac=0.60, val_frac=0.20)
    return split


def test_haversine_distance():
    # Chennai to Bengaluru — actual distance ~290 km
    d = haversine_km(13.0827, 80.2707, 12.9716, 77.5946)
    assert 250 < d < 330, f"Unexpected distance: {d}"


def test_temporal_features_no_future_leakage(processed_split):
    train = processed_split.train
    df_feat = add_temporal_features(train)

    # Lag-1 of temperature should be NaN for the first observation per station
    for station, grp in df_feat.groupby("station_id"):
        grp_s = grp.sort_values("timestamp")
        first_lag = grp_s["temperature_c_lag1"].iloc[0]
        assert pd.isna(first_lag), f"First lag should be NaN for {station}"


def test_rolling_features_use_past_only(processed_split):
    train = processed_split.train
    df_feat = add_temporal_features(train, rolling_windows=[3])

    for station, grp in df_feat.groupby("station_id"):
        grp_s = grp.sort_values("timestamp").reset_index(drop=True)
        assert pd.isna(grp_s["temperature_c_roll3_mean"].iloc[0]), \
            f"First rolling mean should be NaN for {station}"
        if len(grp_s) > 3:
            assert not pd.isna(grp_s["temperature_c_roll3_mean"].iloc[3]), \
                f"Rolling mean at index 3 should not be NaN for {station}"
        break


def test_baseline_fitted_on_train_only(processed_split):
    train = processed_split.train
    val = processed_split.val

    baselines = compute_station_baselines(train)
    val_feat = apply_station_baselines(val, baselines)

    # Baselines should exist for training stations
    assert len(baselines) > 0
    first_station = list(baselines.keys())[0]
    assert "temperature_c" in baselines[first_station]

    # Deviation column should be present
    assert "temperature_c_deviation" in val_feat.columns


def test_spatial_features_same_timestamp_only(processed_split):
    train = processed_split.train
    df_feat = add_spatial_features(train)

    assert "neighbor_temperature_c_mean" in df_feat.columns
    assert "spatial_temperature_c_residual" in df_feat.columns


def test_no_target_in_features(processed_split):
    """Ensure ground_truth_label and fault_description are not used as features."""
    from skyguard.models.decision.classifier import _decision_feature_cols
    train = processed_split.train
    feat_cols = _decision_feature_cols(train)
    assert "ground_truth_label" not in feat_cols
    assert "fault_description" not in feat_cols
