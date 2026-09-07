"""Tests for data loading, validation, and splitting."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from skyguard.config.settings import settings
from skyguard.data.loader import load_raw
from skyguard.data.splitter import chronological_split
from skyguard.data.validator import validate


@pytest.fixture
def raw_df() -> pd.DataFrame:
    return load_raw(settings.raw_data_path)


def test_load_shape(raw_df):
    assert len(raw_df) >= 500
    assert raw_df.shape[1] >= 10
    assert "station_id" in raw_df.columns
    assert "temperature_c" in raw_df.columns


def test_timestamp_parsed(raw_df):
    assert pd.api.types.is_datetime64_any_dtype(raw_df["timestamp"])
    assert raw_df["timestamp"].isna().sum() == 0


def test_station_identifiers(raw_df):
    assert raw_df["station_id"].nunique() >= 3
    assert raw_df["latitude"].notna().all()
    assert raw_df["longitude"].notna().all()


def test_no_duplicate_station_timestamps(raw_df):
    dups = raw_df.duplicated(subset=["station_id", "timestamp"]).sum()
    assert dups == 0


def test_chronological_split_no_leakage(raw_df):
    from skyguard.preprocessing.pipeline import run_preprocessing
    df_proc = run_preprocessing(raw_df)
    split = chronological_split(df_proc, train_frac=0.60, val_frac=0.20)

    assert split.train["timestamp"].max() <= split.val["timestamp"].min()
    assert split.val["timestamp"].max() <= split.test["timestamp"].min()


def test_split_sizes(raw_df):
    from skyguard.preprocessing.pipeline import run_preprocessing
    df_proc = run_preprocessing(raw_df)
    split = chronological_split(df_proc, train_frac=0.60, val_frac=0.20)

    total = len(split.train) + len(split.val) + len(split.test)
    assert total == len(df_proc)


def test_validation_report(raw_df):
    report = validate(raw_df)
    assert report.is_valid
