"""Test suite for Historical AWS Data Storage, Continuous Training, Excel Partitioning, and Historical APIs."""

import io
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import app
from skyguard.services.historical_data_manager import HistoricalDataManager
from skyguard.services.historical_data_provider import HistoricalDataProvider, IMDHistoricalDataProvider
from skyguard.services.historical_exporter import HistoricalExporter
from skyguard.services.historical_store import HistoricalStore
from skyguard.services.live_data_manager import LiveDataManager
from skyguard.training.feature_pipeline import TrainingFeaturePipeline
from skyguard.training.historical_dataset_builder import HistoricalDatasetBuilder
from skyguard.training.model_trainer import MultiModelTrainer
from skyguard.training.training_manager import ContinuousTrainingManager


class MockHistoricalProvider(HistoricalDataProvider):
    """Test mock for HistoricalDataProvider."""

    def __init__(self, records=None):
        self.records = records or []

    def fetch(self, start_datetime, end_datetime, station_ids=None):
        return self.records, None

    def get_provider_status(self):
        return {"provider": "Mock Provider", "source": "test"}


@pytest.fixture
def temp_db_path(tmp_path):
    return tmp_path / "test_historical.db"


@pytest.fixture
def temp_export_dir(tmp_path):
    return tmp_path / "test_exports"


@pytest.fixture
def sample_historical_records():
    records = []
    base_time = datetime(2023, 1, 1, 0, 0, 0)
    for stn_id in ["STN_DELHI", "STN_MUMBAI", "STN_KOLKATA"]:
        for i in range(10):
            ts = (base_time + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S")
            records.append({
                "timestamp": ts,
                "station_id": stn_id,
                "station_name": f"{stn_id} AWS",
                "district": "Metropolitan",
                "state": "National",
                "latitude": 28.6139 if "DELHI" in stn_id else 19.0760,
                "longitude": 77.2090 if "DELHI" in stn_id else 72.8777,
                "temperature_c": 25.0 + i * 0.5,
                "relative_humidity_pct": 60.0 - i * 0.8,
                "pressure_hpa": 1012.0 - i * 0.2,
                "wind_speed_kmh": 10.0 + i * 0.3,
                "rainfall_mm": 0.0,
                "ground_truth_label": "NORMAL" if i < 8 else "SENSOR_FAULT",
                "fault_description": "None" if i < 8 else "SPIKE",
            })
    return records


# ── 1. Historical Store Tests ──────────────────────────────────────────────────

def test_historical_store_crud_and_duplicate_prevention(temp_db_path, sample_historical_records):
    store = HistoricalStore(db_path=temp_db_path)

    # Initial insertion
    inserted = store.insert_observations(sample_historical_records)
    assert inserted == len(sample_historical_records)

    # Duplicate insertion attempt — must be silently ignored without throwing or duplicating
    dup_inserted = store.insert_observations(sample_historical_records)
    assert dup_inserted == 0

    # Query observations
    obs = store.get_observations(station_id="STN_DELHI")
    assert len(obs) == 10
    assert obs[0]["station_id"] == "STN_DELHI"

    # Status check
    status = store.get_status()
    assert status["available"] is True
    assert status["stations"] == 3
    assert status["records"] == 30
    assert status["oldest_observation"] == "2023-01-01 00:00:00"
    assert status["latest_observation"] == "2023-01-01 09:00:00"


def test_historical_adaptive_downsampling(temp_db_path):
    store = HistoricalStore(db_path=temp_db_path)
    base_time = datetime(2020, 1, 1, 0, 0, 0)

    # Generate 500 records
    large_records = []
    for i in range(500):
        ts = (base_time + timedelta(hours=i * 6)).strftime("%Y-%m-%d %H:%M:%S")
        large_records.append({
            "timestamp": ts,
            "station_id": "STN_LONG_HISTORY",
            "station_name": "Long History AWS",
            "latitude": 20.0,
            "longitude": 78.0,
            "temperature_c": 30.0 + (i % 10),
            "relative_humidity_pct": 50.0,
            "pressure_hpa": 1000.0,
            "wind_speed_kmh": 12.0,
            "rainfall_mm": 0.0,
            "ground_truth_label": "NORMAL" if i % 20 != 0 else "GENUINE_EXTREME",
        })
    store.insert_observations(large_records)

    # Request max_points = 50
    adaptive = store.get_station_history_adaptive(station_id="STN_LONG_HISTORY", max_points=50)
    assert adaptive["total_records"] == 500
    assert adaptive["displayed_points"] <= 60
    assert len(adaptive["points"]) <= 60
    assert len(adaptive["anomalies"]) > 0
    assert adaptive["latest_observation"] is not None


# ── 2. Live Persistence to Historical Store ────────────────────────────────────

def test_live_observation_persisted_to_store(temp_db_path):
    store = HistoricalStore(db_path=temp_db_path)
    exporter = HistoricalExporter(store=store)
    mgr = LiveDataManager(store=store, exporter=exporter, data_source="imd")

    live_obs = [{
        "timestamp": "2026-09-21 16:00:00",
        "station_id": "LIVE_STN_001",
        "station_name": "Live Station 001",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "temperature_c": 34.2,
        "relative_humidity_pct": 68.0,
        "pressure_hpa": 1008.5,
        "wind_speed_kmh": 14.0,
        "rainfall_mm": 0.0,
    }]

    mgr.ingest_live_observations(live_obs)

    # Verify live record was persisted to SQLite
    stored_obs = store.get_observations(station_id="LIVE_STN_001")
    assert len(stored_obs) == 1
    assert stored_obs[0]["timestamp"] == "2026-09-21 16:00:00"
    assert stored_obs[0]["temperature_c"] == 34.2

    # Verify get_station_history returns from persistent store
    hist = mgr.get_station_history("LIVE_STN_001")
    assert len(hist) == 1
    assert hist[0]["station_id"] == "LIVE_STN_001"


# ── 3. Excel Partitioning & Export ─────────────────────────────────────────────

def test_excel_export_and_partitioning(temp_db_path, temp_export_dir, sample_historical_records):
    store = HistoricalStore(db_path=temp_db_path)
    store.insert_observations(sample_historical_records)

    exporter = HistoricalExporter(store=store, export_dir=temp_export_dir)
    res = exporter.export_full_archive()

    assert res["success"] is True
    assert res["total_rows_exported"] == 30
    assert len(res["files_created"]) > 0

    # Verify partition file exists on disk
    part_file = Path(res["files_created"][0])
    assert part_file.exists()
    assert part_file.suffix == ".xlsx"

    # In-memory buffer export test (xlsx and csv)
    buf_xlsx, name_xlsx, mime_xlsx = exporter.export_data_buffer(export_format="xlsx")
    assert buf_xlsx.getbuffer().nbytes > 0
    assert name_xlsx.endswith(".xlsx")
    assert "spreadsheetml" in mime_xlsx

    buf_csv, name_csv, mime_csv = exporter.export_data_buffer(export_format="csv")
    assert buf_csv.getbuffer().nbytes > 0
    assert name_csv.endswith(".csv")
    assert mime_csv == "text/csv"


# ── 4. Chronological Splitting & Training ──────────────────────────────────────

def test_chronological_split_no_future_leakage(temp_db_path, sample_historical_records):
    store = HistoricalStore(db_path=temp_db_path)
    store.insert_observations(sample_historical_records)

    builder = HistoricalDatasetBuilder(store=store)
    df = builder.load_dataset()
    train_df, val_df, test_df, audit = builder.prepare_training_splits(
        df, train_ratio=0.60, val_ratio=0.20
    )

    # Verify temporal ordering: max train timestamp <= min val timestamp
    assert train_df["timestamp"].max() <= val_df["timestamp"].min()
    assert val_df["timestamp"].max() <= test_df["timestamp"].min()

    # Verify audit metrics
    assert audit.total_records == 30
    assert audit.unique_stations == 3
    assert audit.duplicate_records == 0


def test_model_trainer_pipeline(temp_db_path, sample_historical_records):
    store = HistoricalStore(db_path=temp_db_path)
    store.insert_observations(sample_historical_records)

    builder = HistoricalDatasetBuilder(store=store)
    df = builder.load_dataset()
    train_df, val_df, test_df, _ = builder.prepare_training_splits(df, train_ratio=0.60, val_ratio=0.20)

    feat_pipe = TrainingFeaturePipeline()
    train_feat, _ = feat_pipe.fit_transform_train(train_df)
    val_feat = feat_pipe.transform_eval(val_df)

    trainer = MultiModelTrainer()
    results = trainer.train_all_models(train_df=train_feat, val_df=val_feat)

    assert "expected_models" in results
    assert "temperature_c" in results["expected_models"]
    assert "anomaly_detector" in results
    assert "decision_classifier" in results
    assert "val_macro_f1" in results["metrics"]


# ── 5. FastAPI Historical & Training Endpoints ─────────────────────────────────

def test_historical_api_endpoints():
    client = TestClient(app)

    # 1. GET /historical/status
    r_status = client.get("/historical/status")
    assert r_status.status_code == 200
    st_data = r_status.json()
    assert "available" in st_data
    assert "stations" in st_data
    assert "records" in st_data

    # 2. GET /historical/stations/{id}
    # Query an existing or sample station ID
    r_hist = client.get("/historical/stations/STN_TEST_001")
    assert r_hist.status_code == 200
    hist_data = r_hist.json()
    assert "station_id" in hist_data
    assert "points" in hist_data

    # 3. GET /historical/export (CSV)
    r_export = client.get("/historical/export?format=csv")
    assert r_export.status_code == 200
    assert "text/csv" in r_export.headers.get("content-type", "")

    # 4. POST /training/start
    r_train = client.post("/training/start", json={"train_ratio": 0.70, "val_ratio": 0.15})
    assert r_train.status_code == 200
    train_data = r_train.json()
    assert train_data["status"] == "started"
    assert "training_id" in train_data

    # 5. GET /training/status
    tid = train_data["training_id"]
    r_tstatus = client.get(f"/training/status?training_id={tid}")
    assert r_tstatus.status_code == 200

    # 6. GET /training/history
    r_history = client.get("/training/history")
    assert r_history.status_code == 200
    assert "runs" in r_history.json()
