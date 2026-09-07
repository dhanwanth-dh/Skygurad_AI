"""FastAPI application — SkyGuard Multi-Model Intelligence Inference API."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from skyguard.config.settings import settings
from skyguard.data.loader import load_raw
from skyguard.inference.predictor import SkyGuardPredictor
from api.schemas import (
    AnomalyConsensus,
    AnomalyListResponse,
    AnomalyRecord,
    HealthResponse,
    HistoryRecord,
    HistoryResponse,
    ModelInfoResponse,
    ModelRegistryItem,
    ModelRegistryResponse,
    PredictionResponse,
    StationListResponse,
    StationRecord,
    WeatherObservation,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("skyguard.api")

# ── Global state ───────────────────────────────────────────────────────────────
_predictor: SkyGuardPredictor | None = None
_dataset: pd.DataFrame | None = None  # raw CSV, loaded once at startup
_station_cache: list[StationRecord] | None = None
_anomaly_cache: list[AnomalyRecord] | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _predictor, _dataset
    try:
        _predictor = _get_predictor()
        logger.info("SkyGuard Multi-Model predictor loaded successfully.")
    except Exception as exc:
        logger.error("Failed to load predictor: %s", exc)
        _predictor = None

    _dataset = _get_dataset()
    _refresh_station_cache()
    yield


app = FastAPI(
    title="SkyGuard AI — Multi-Model Intelligence Engine API",
    description="Multi-Model Predictive Weather Station Quality Control & Fault Intelligence",
    version="2.0.0",
    lifespan=lifespan,
)

_raw_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
_allow_all = "*" in _origins or not _origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _allow_all else _origins,
    allow_credentials=not _allow_all,
    allow_methods=["*"],
    allow_headers=["*"],
)



def _load_dataset() -> pd.DataFrame | None:
    """Load the raw CSV dataset once at startup."""
    try:
        path = settings.raw_data_path
        df = load_raw(path)
        logger.info("Dataset loaded: %d rows, %d stations", len(df), df["station_id"].nunique())
        return df
    except Exception as exc:
        logger.error("Failed to load dataset: %s", exc)
        return None


def _get_predictor() -> SkyGuardPredictor:
    """Lazy loader for the predictor instance."""
    global _predictor
    if _predictor is None:
        _predictor = SkyGuardPredictor(settings.artifacts_dir)
        _predictor.load()
    return _predictor


def _get_dataset() -> pd.DataFrame | None:
    """Lazy loader for dataset."""
    global _dataset
    if _dataset is None:
        _dataset = _load_dataset()
    return _dataset


def _refresh_station_cache() -> None:
    """Pre-compute inference on latest rows per station for fast responses."""
    global _station_cache, _anomaly_cache
    ds = _get_dataset()
    if ds is None:
        return

    latest_rows = (
        ds.sort_values("timestamp")
        .groupby("station_id", sort=False)
        .tail(1)
    )

    records: list[StationRecord] = []
    anomalies: list[AnomalyRecord] = []

    for _, row in latest_rows.iterrows():
        obs = _row_to_obs(row)
        try:
            inf = _run_inference(obs)
        except Exception as exc:
            logger.warning("Inference failed for %s: %s", row["station_id"], exc)
            inf = {
                "prediction": "UNKNOWN", "confidence": 0.0, "confidence_level": "LOW",
                "uncertainty_score": 0.5, "anomaly_score": 0.0, "anomaly_consensus": None,
                "model_agreement": 1.0, "model_coverage": "0/6 active",
                "fault_type": "NONE", "fault_confidence": 0.0, "fault_evidence": [],
                "genuine_event_score": 0.0, "genuine_event_evidence": [],
                "severity": "LOW", "sensor_health": 100.0, "sensor_health_status": "UNKNOWN",
                "expected_values": {}, "observed_values": {},
                "top_reasons": [], "recommended_action": None, "correction": {},
            }

        rec = StationRecord(
            station_id=str(row["station_id"]),
            station_name=str(row.get("station_name", "")) or None,
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            latest_timestamp=str(row["timestamp"]),
            temperature_c=float(row["temperature_c"]),
            relative_humidity_pct=float(row["relative_humidity_pct"]),
            pressure_hpa=float(row["pressure_hpa"]),
            wind_speed_kmh=float(row.get("wind_speed_kmh", 0.0)) if pd.notna(row.get("wind_speed_kmh")) else 0.0,
            rainfall_mm=float(row.get("rainfall_mm", 0.0)) if pd.notna(row.get("rainfall_mm")) else 0.0,
            prediction=inf["prediction"],
            confidence=inf["confidence"],
            confidence_level=inf.get("confidence_level", "MEDIUM"),
            uncertainty_score=inf.get("uncertainty_score", 0.0),
            anomaly_score=inf["anomaly_score"],
            anomaly_consensus=AnomalyConsensus(**inf["anomaly_consensus"]) if inf.get("anomaly_consensus") else None,
            model_agreement=inf.get("model_agreement", 1.0),
            model_coverage=inf.get("model_coverage", "6/6 active"),
            fault_type=inf["fault_type"],
            fault_confidence=inf.get("fault_confidence", 0.0),
            fault_evidence=inf.get("fault_evidence", []),
            genuine_event_score=inf.get("genuine_event_score", 0.0),
            genuine_event_evidence=inf.get("genuine_event_evidence", []),
            severity=inf["severity"],
            sensor_health=inf["sensor_health"],
            sensor_health_status=inf["sensor_health_status"],
            expected_values=inf["expected_values"],
            observed_values=inf["observed_values"],
            top_reasons=inf["top_reasons"],
            recommended_action=inf.get("recommended_action"),
            correction=inf["correction"],
        )
        records.append(rec)

        if inf["prediction"] != "NORMAL":
            anomalies.append(AnomalyRecord(
                station_id=rec.station_id,
                station_name=rec.station_name,
                latitude=rec.latitude,
                longitude=rec.longitude,
                timestamp=rec.latest_timestamp,
                prediction=rec.prediction,
                confidence=rec.confidence,
                confidence_level=rec.confidence_level,
                uncertainty_score=rec.uncertainty_score,
                anomaly_score=rec.anomaly_score,
                anomaly_consensus=rec.anomaly_consensus,
                model_agreement=rec.model_agreement,
                fault_type=rec.fault_type,
                fault_confidence=rec.fault_confidence,
                fault_evidence=rec.fault_evidence,
                genuine_event_score=rec.genuine_event_score,
                genuine_event_evidence=rec.genuine_event_evidence,
                severity=rec.severity,
                sensor_health=rec.sensor_health,
                sensor_health_status=rec.sensor_health_status,
                expected_values=rec.expected_values,
                observed_values=rec.observed_values,
                top_reasons=rec.top_reasons,
                recommended_action=rec.recommended_action,
                correction=rec.correction,
            ))

    _station_cache = records
    _anomaly_cache = anomalies
    logger.info("Station cache refreshed (%d stations, %d anomalies).", len(records), len(anomalies))

# ── Helpers ────────────────────────────────────────────────────────────────────

def _row_to_obs(row: pd.Series) -> dict:
    """Convert a dataset row to a WeatherObservation-compatible dict."""
    wind = float(row.get("wind_speed_kmh", 0.0)) if pd.notna(row.get("wind_speed_kmh")) else 0.0
    rain = float(row.get("rainfall_mm", 0.0)) if pd.notna(row.get("rainfall_mm")) else 0.0
    return {
        "timestamp": str(row["timestamp"]),
        "station_id": str(row["station_id"]),
        "station_name": str(row.get("station_name", "")) or None,
        "latitude": float(row["latitude"]),
        "longitude": float(row["longitude"]),
        "temperature_c": float(row["temperature_c"]),
        "relative_humidity_pct": float(row["relative_humidity_pct"]),
        "pressure_hpa": float(row["pressure_hpa"]),
        "wind_speed_kmh": wind,
        "rainfall_mm": rain,
    }


def _run_inference(obs: dict) -> dict:
    """Run predictor on a single observation dict."""
    pred = _get_predictor()
    return pred.predict_single(obs)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.post("/predict", response_model=PredictionResponse)
async def predict(observation: WeatherObservation) -> PredictionResponse:
    try:
        pred = _get_predictor()
        result = pred.predict_single(observation.model_dump())
        return PredictionResponse(**result)
    except Exception as exc:
        logger.exception("Prediction failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    pred = _get_predictor()
    return HealthResponse(
        status="ok",
        model_loaded=pred is not None,
        version=pred._model_version if pred else "not_loaded",
    )


@app.get("/model-info", response_model=ModelInfoResponse)
async def model_info() -> ModelInfoResponse:
    pred = _get_predictor()
    meta_path = settings.artifacts_dir / "metadata" / "model_metadata.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Model metadata not found.")
    with open(meta_path) as f:
        meta = json.load(f)

    reg_raw = meta.get("model_registry", [])
    registry_items = [ModelRegistryItem(**item) for item in reg_raw] if reg_raw else []

    return ModelInfoResponse(
        model_version=meta.get("model_version", "unknown"),
        decision_model=meta.get("decision_model", "unknown"),
        val_macro_f1=float(meta.get("val_macro_f1", 0.0)),
        train_date=meta.get("train_date", "unknown"),
        classes=[str(c) for c in pred._decision_clf.classes_] if (pred and hasattr(pred, "_decision_clf") and pred._decision_clf is not None) else ["NORMAL", "GENUINE_EXTREME", "SENSOR_FAULT"],
        model_registry=registry_items,
    )


@app.get("/model-registry", response_model=ModelRegistryResponse)
async def get_model_registry() -> ModelRegistryResponse:
    """Return the complete multi-model registry with validation metrics and statuses."""
    meta_path = settings.artifacts_dir / "metadata" / "model_metadata.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Model metadata not found.")
    with open(meta_path) as f:
        meta = json.load(f)

    reg_raw = meta.get("model_registry", [])
    registry_items = [ModelRegistryItem(**item) for item in reg_raw]

    active_count = sum(1 for item in registry_items if item.status == "ACTIVE")
    disabled_count = sum(1 for item in registry_items if item.status != "ACTIVE")

    return ModelRegistryResponse(
        model_version=meta.get("model_version", "unknown"),
        train_date=meta.get("train_date", "unknown"),
        total_models=len(registry_items),
        active_models=active_count,
        disabled_models=disabled_count,
        registry=registry_items,
    )


@app.get("/stations", response_model=StationListResponse)
async def get_stations() -> StationListResponse:
    """Return all unique AWS stations with their latest observation + inference."""
    global _station_cache
    if _station_cache is None:
        _refresh_station_cache()
    if _station_cache is None:
        raise HTTPException(status_code=503, detail="Dataset not loaded.")
    return StationListResponse(stations=_station_cache, total=len(_station_cache))


@app.get("/anomalies", response_model=AnomalyListResponse)
async def get_anomalies() -> AnomalyListResponse:
    """Return only anomalous observations (prediction != NORMAL) from latest per station."""
    global _anomaly_cache
    if _anomaly_cache is None:
        _refresh_station_cache()
    if _anomaly_cache is None:
        raise HTTPException(status_code=503, detail="Dataset not loaded.")

    sensor_faults = sum(1 for a in _anomaly_cache if a.prediction == "SENSOR_FAULT")
    genuine_events = sum(1 for a in _anomaly_cache if a.prediction == "GENUINE_EXTREME")

    return AnomalyListResponse(
        anomalies=_anomaly_cache,
        total=len(_anomaly_cache),
        sensor_faults=sensor_faults,
        genuine_events=genuine_events,
    )


@app.get("/stations/{station_id}/history", response_model=HistoryResponse)
async def get_station_history(station_id: str) -> HistoryResponse:
    """Return chronological observations for a specific station from the dataset."""
    ds = _get_dataset()
    if ds is None:
        raise HTTPException(status_code=503, detail="Dataset not loaded.")

    station_df = ds[ds["station_id"] == station_id].sort_values("timestamp")
    if station_df.empty:
        raise HTTPException(status_code=404, detail=f"Station '{station_id}' not found.")

    # Return the most recent 100 observations to keep response fast
    recent_df = station_df.tail(100)
    records: list[HistoryRecord] = []
    for _, row in recent_df.iterrows():
        records.append(HistoryRecord(
            timestamp=str(row["timestamp"]),
            temperature_c=float(row["temperature_c"]),
            relative_humidity_pct=float(row["relative_humidity_pct"]),
            pressure_hpa=float(row["pressure_hpa"]),
            wind_speed_kmh=float(row.get("wind_speed_kmh", 0.0)) if pd.notna(row.get("wind_speed_kmh")) else 0.0,
            rainfall_mm=float(row.get("rainfall_mm", 0.0)) if pd.notna(row.get("rainfall_mm")) else 0.0,
            ground_truth_label=str(row["ground_truth_label"]) if pd.notna(row.get("ground_truth_label")) else None,
            fault_description=str(row["fault_description"]) if pd.notna(row.get("fault_description")) else None,
        ))

    return HistoryResponse(
        station_id=station_id,
        records=records,
        total=len(records),
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)
