"""Unit and Integration Tests for IMD Live AWS Ingestion Layer and SkyGuard AI Pipeline."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skyguard.config.settings import settings
from skyguard.inference.predictor import SkyGuardPredictor
from skyguard.services.imd_auth import IMDAuthService
from skyguard.services.imd_client import IMDClient
from skyguard.services.imd_normalizer import IMDNormalizer
from skyguard.services.live_data_manager import LiveDataManager
from api.schemas import StationRecord, AnomalyRecord, PredictionResponse, WeatherObservation


# ── 1. IMD Auth Service Tests ──────────────────────────────────────────────────

def test_imd_auth_service_token_request():
    auth = IMDAuthService(email="test@example.com", password="password123")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "access_token": "mock_jwt_token_xyz",
        "token_type": "Bearer",
        "expires_in": 3600,
    }

    with patch("requests.post", return_value=mock_resp):
        token, err = auth.get_valid_token()
        assert err is None
        assert token == "mock_jwt_token_xyz"
        assert auth.is_authenticated() is True


def test_imd_auth_service_caching():
    auth = IMDAuthService(email="test@example.com", password="password123")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "access_token": "cached_jwt_token",
        "expires_in": 3600,
    }

    with patch("requests.post", return_value=mock_resp) as mock_post:
        token1, _ = auth.get_valid_token()
        token2, _ = auth.get_valid_token()
        assert token1 == token2 == "cached_jwt_token"
        assert mock_post.call_count == 1  # Reused from cache without repeating network calls


# ── 2. IMD Client Tests ────────────────────────────────────────────────────────

def test_imd_client_payload_extraction():
    client = IMDClient()
    # List format
    data_list = [{"ID": "AWS_01", "CURR_TEMP": 28.5}]
    assert len(client._extract_records_from_payload(data_list)) == 1

    # Dict with data key
    data_dict = {"data": [{"ID": "AWS_01", "CURR_TEMP": 28.5}], "status": "success"}
    assert len(client._extract_records_from_payload(data_dict)) == 1

    # Single observation dict
    single_dict = {"ID": "AWS_01", "CURR_TEMP": 28.5, "Latitude": 17.5}
    assert len(client._extract_records_from_payload(single_dict)) == 1


def test_imd_client_mock_fetch_success():
    auth = MagicMock()
    auth.get_valid_token.return_value = ("mock_jwt", None)
    client = IMDClient(api_key="test_key", auth_service=auth)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {
            "ID": "4952C57C",
            "DISTRICT": "UTTARKASHI",
            "STATE": "UTTARAKHAND",
            "STATION": "PUROLA",
            "DATE": "2026-09-21",
            "TIME": "09:15:00",
            "CURR_TEMP": "33.3",
            "RH": "55",
            "MSLP": "889.7",
            "WIND_SPEED": 0,
            "Latitude": "30.86",
            "Longitude": "78",
            "RAINFALL": "0.0",
        }
    ]

    with patch.object(client._session, "get", return_value=mock_resp):
        records, err = client.fetch_raw_observations()
        assert err is None
        assert records is not None
        assert len(records) == 1
        assert records[0]["ID"] == "4952C57C"


def test_imd_client_error_handling():
    auth = MagicMock()
    auth.get_valid_token.return_value = ("mock_jwt", None)
    client = IMDClient(api_key="invalid_key", auth_service=auth)

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = '{"error":"Unauthorised"}'

    with patch.object(client._session, "get", return_value=mock_resp):
        records, err = client.fetch_raw_observations()
        assert records is None
        assert err is not None
        assert "401" in err


# ── 3. IMD Normalizer Tests ───────────────────────────────────────────────────

def test_normalizer_live_imd_schema():
    raw = {
        "ID": "4952C57C",
        "CALL_SIGN": None,
        "DISTRICT": "UTTARKASHI",
        "STATE": "UTTARAKHAND",
        "STATION": "PUROLA",
        "DATE": "2026-09-21",
        "TIME": "09:15:00",
        "CURR_TEMP": "33.3",
        "DEW_POINT_TEMP": None,
        "RH": "55",
        "WIND_DIRECTION": 0,
        "WIND_SPEED": 0,
        "MSLP": "889.7",
        "MIN_TEMP": "15.2",
        "MAX_TEMP": "35.9",
        "Latitude": "30.86",
        "Longitude": "78",
        "WEATHER_CODE": "0",
        "NEBULOSITY": "0",
        "RAINFALL_SEL": "NULL",
        "RAINFALL": "0.0",
        "Feel Like": "38.5",
        "WEATHER_ICON": "100-fill",
        "WEATHER_MESSAGE": "Clear Sky",
    }
    rec = IMDNormalizer.normalize_record(raw)
    assert rec is not None
    assert rec["station_id"] == "4952C57C"
    assert "PUROLA" in rec["station_name"]
    assert rec["latitude"] == 30.86
    assert rec["longitude"] == 78.0
    assert rec["temperature_c"] == 33.3
    assert rec["relative_humidity_pct"] == 55.0
    assert rec["pressure_hpa"] == 889.7
    assert rec["wind_speed_kmh"] == 0.0
    assert rec["rainfall_mm"] == 0.0
    assert rec["timestamp"] == "2026-09-21 09:15:00"


def test_normalizer_unit_conversions():
    # Test m/s to km/h, Pa to hPa, cm to mm, Fahrenheit to Celsius
    raw = {
        "station_id": "AWS_CONV_01",
        "station_name": "Conversion Test AWS",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "timestamp": "2025-06-15 12:00:00",
        "temperature": 86.0,
        "relative_humidity": 65.0,
        "pressure": 101325.0,  # 101325 Pa -> 1013.25 hPa
        "wind_speed_ms": 10.0,  # 10 m/s -> 36.0 km/h
        "rainfall_cm": 2.5,  # 2.5 cm -> 25.0 mm
    }
    rec = IMDNormalizer.normalize_record(raw)
    assert rec is not None
    assert abs(rec["pressure_hpa"] - 1013.25) < 0.1
    assert abs(rec["wind_speed_kmh"] - 36.0) < 0.1
    assert abs(rec["rainfall_mm"] - 25.0) < 0.1


def test_normalizer_missing_values_sanitization():
    raw = {
        "station_id": "AWS_NULL_01",
        "latitude": 22.5726,
        "longitude": 88.3639,
        "timestamp": "2025-06-15 12:00:00",
        "temperature_c": "NA",
        "relative_humidity_pct": "-",
        "pressure_hpa": "-999.0",
        "wind_speed_kmh": "null",
        "rainfall_mm": "",
    }
    rec = IMDNormalizer.normalize_record(raw)
    assert rec is not None
    assert rec["temperature_c"] == 25.0  # safe default fallback
    assert rec["pressure_hpa"] == 1013.25  # standard atmospheric pressure default
    assert rec["wind_speed_kmh"] == 0.0
    assert rec["rainfall_mm"] == 0.0


def test_normalizer_batch_deduplication():
    records = [
        {"station_id": "AWS_01", "timestamp": "2025-06-15 10:00:00", "temp": 28.0, "latitude": 20.0, "longitude": 78.0},
        {"station_id": "AWS_01", "timestamp": "2025-06-15 10:00:00", "temp": 28.0, "latitude": 20.0, "longitude": 78.0},  # duplicate
        {"station_id": "AWS_02", "timestamp": "2025-06-15 10:00:00", "temp": 30.0, "latitude": 21.0, "longitude": 79.0},
    ]
    batch = IMDNormalizer.normalize_batch(records)
    assert len(batch) == 2


# ── 4. Live Data Manager & Pipeline Integration Tests ─────────────────────────

def test_live_data_manager_synthetic_mode():
    predictor = SkyGuardPredictor(settings.artifacts_dir).load()
    manager = LiveDataManager(predictor=predictor, data_source="synthetic")
    manager.initialize()

    stations = manager.get_stations()
    assert len(stations) > 0
    anomalies = manager.get_anomalies()
    assert isinstance(anomalies, list)

    status = manager.get_status()
    assert status["data_source"] == "synthetic"
    assert status["stations_monitored"] == len(stations)


def test_live_data_manager_imd_mode_with_mock():
    predictor = SkyGuardPredictor(settings.artifacts_dir).load()
    client = MagicMock()
    client.fetch_raw_observations.return_value = (
        [
            {
                "ID": "AWS_HYD_01",
                "STATION": "Hyderabad AWS",
                "Latitude": 17.3850,
                "Longitude": 78.4867,
                "DATE": "2026-09-21",
                "TIME": "15:00:00",
                "CURR_TEMP": 34.2,
                "RH": 55.0,
                "MSLP": 1005.1,
                "WIND_SPEED": 12.0,
                "RAINFALL": 0.0,
            },
            {
                "ID": "AWS_BLR_01",
                "STATION": "Bengaluru AWS",
                "Latitude": 12.9716,
                "Longitude": 77.5946,
                "DATE": "2026-09-21",
                "TIME": "15:00:00",
                "CURR_TEMP": 26.8,
                "RH": 72.0,
                "MSLP": 920.0,
                "WIND_SPEED": 8.5,
                "RAINFALL": 1.2,
            },
        ],
        None,
    )

    manager = LiveDataManager(predictor=predictor, imd_client=client, data_source="imd")
    manager.initialize()

    stations = manager.get_stations()
    assert len(stations) == 2
    station_ids = [s["station_id"] for s in stations]
    assert "AWS_HYD_01" in station_ids
    assert "AWS_BLR_01" in station_ids

    # Verify AI inference results populated
    for s in stations:
        assert s["prediction"] in ("NORMAL", "GENUINE_EXTREME", "SENSOR_FAULT", "UNKNOWN")
        assert 0.0 <= s["confidence"] <= 1.0
        assert "expected_values" in s
        assert "top_reasons" in s

    # Verify History retrieval
    history = manager.get_station_history("AWS_HYD_01")
    assert len(history) >= 1
    assert history[0]["temperature_c"] == 34.2


def test_end_to_end_imd_observation_to_schemas():
    """Verify that a normalized IMD observation produces a valid StationRecord Pydantic object."""
    predictor = SkyGuardPredictor(settings.artifacts_dir).load()
    raw_imd_obs = {
        "ID": "IMD_CHENNAI_AWS",
        "STATION": "Chennai Meenambakkam AWS",
        "Latitude": 13.0012,
        "Longitude": 80.1800,
        "DATE": "2026-09-21",
        "TIME": "16:00:00",
        "CURR_TEMP": 36.4,
        "RH": 68.5,
        "MSLP": 1004.2,
        "WIND_SPEED": 22.0,
        "RAINFALL": 0.0,
    }

    normalized = IMDNormalizer.normalize_record(raw_imd_obs)
    assert normalized is not None

    # Run full predictor
    inference_result = predictor.predict_single(normalized)
    assert inference_result["prediction"] in ("NORMAL", "GENUINE_EXTREME", "SENSOR_FAULT")

    # Construct StationRecord Pydantic model exactly as API does
    station_dict = {
        "station_id": normalized["station_id"],
        "station_name": normalized["station_name"],
        "latitude": normalized["latitude"],
        "longitude": normalized["longitude"],
        "latest_timestamp": normalized["timestamp"],
        "temperature_c": normalized["temperature_c"],
        "relative_humidity_pct": normalized["relative_humidity_pct"],
        "pressure_hpa": normalized["pressure_hpa"],
        "wind_speed_kmh": normalized["wind_speed_kmh"],
        "rainfall_mm": normalized["rainfall_mm"],
        **inference_result
    }
    rec = StationRecord(**station_dict)
    assert rec.station_id == "IMD_CHENNAI_AWS"
    assert rec.temperature_c == 36.4
    assert rec.confidence >= 0.0
