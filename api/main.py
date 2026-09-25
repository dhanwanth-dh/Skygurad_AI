"""FastAPI application — SkyGuard Multi-Model Intelligence Inference API."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from skyguard.config.settings import settings
from skyguard.inference.predictor import SkyGuardPredictor
from skyguard.services.historical_exporter import HistoricalExporter
from skyguard.services.historical_store import HistoricalStore
from skyguard.services.live_data_manager import LiveDataManager
from skyguard.training.training_manager import ContinuousTrainingManager
from api.schemas import (
    AdaptiveHistoryResponse,
    AnomalyConsensus,
    AnomalyListResponse,
    AnomalyRecord,
    HealthResponse,
    HistoricalStatusResponse,
    HistoryRecord,
    HistoryResponse,
    ModelInfoResponse,
    ModelRegistryItem,
    ModelRegistryResponse,
    PredictionResponse,
    StationListResponse,
    StationRecord,
    TrainingHistoryResponse,
    TrainingStartRequest,
    TrainingStartResponse,
    TrainingStatusResponse,
    WeatherObservation,
)
from fastapi.responses import StreamingResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("skyguard.api")

# ── Global state ───────────────────────────────────────────────────────────────
_predictor: SkyGuardPredictor | None = None
_data_manager: LiveDataManager | None = None
_training_manager: ContinuousTrainingManager | None = None
_historical_store: HistoricalStore | None = None
_historical_exporter: HistoricalExporter | None = None
_poll_task: asyncio.Task | None = None


def _get_historical_store() -> HistoricalStore:
    """Lazy loader for persistent HistoricalStore."""
    global _historical_store
    if _historical_store is None:
        _historical_store = HistoricalStore()
    return _historical_store


def _get_historical_exporter() -> HistoricalExporter:
    """Lazy loader for HistoricalExporter."""
    global _historical_exporter
    if _historical_exporter is None:
        _historical_exporter = HistoricalExporter(store=_get_historical_store())
    return _historical_exporter


def _get_training_manager() -> ContinuousTrainingManager:
    """Lazy loader for ContinuousTrainingManager."""
    global _training_manager
    if _training_manager is None:
        _training_manager = ContinuousTrainingManager(store=_get_historical_store())
    return _training_manager


def _get_predictor() -> SkyGuardPredictor:
    """Lazy loader for the predictor instance."""
    global _predictor
    if _predictor is None:
        _predictor = SkyGuardPredictor(settings.artifacts_dir)
        _predictor.load()
    return _predictor


def _get_data_manager() -> LiveDataManager:
    """Lazy loader for the LiveDataManager instance."""
    global _data_manager
    if _data_manager is None:
        pred = _get_predictor()
        store = _get_historical_store()
        exporter = _get_historical_exporter()
        _data_manager = LiveDataManager(predictor=pred, store=store, exporter=exporter)
        _data_manager.initialize()
    return _data_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _predictor, _data_manager, _poll_task
    try:
        _predictor = _get_predictor()
        logger.info("SkyGuard Multi-Model predictor loaded successfully.")
    except Exception as exc:
        logger.error("Failed to load predictor: %s", exc)
        _predictor = None

    try:
        _data_manager = _get_data_manager()
        logger.info("SkyGuard LiveDataManager initialized successfully.")
    except Exception as exc:
        logger.error("Failed to initialize LiveDataManager: %s", exc)
        _data_manager = None

    # Start background polling loop if in live IMD mode
    if _data_manager and settings.data_source == "imd":
        _poll_task = asyncio.create_task(_data_manager.start_polling())

    yield

    # Teardown background polling
    if _poll_task:
        _poll_task.cancel()
        try:
            await _poll_task
        except asyncio.CancelledError:
            pass


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


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.post("/predict", response_model=PredictionResponse)
async def predict(observation: WeatherObservation) -> PredictionResponse:
    """Run real-time multi-model inference pipeline on a single AWS observation."""
    try:
        pred = _get_predictor()
        result = pred.predict_single(observation.model_dump())
        return PredictionResponse(**result)
    except Exception as exc:
        logger.exception("Prediction failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Check API health and model readiness."""
    pred = _get_predictor()
    return HealthResponse(
        status="ok",
        model_loaded=pred is not None,
        version=pred._model_version if pred else "not_loaded",
    )


@app.get("/model-info", response_model=ModelInfoResponse)
async def model_info() -> ModelInfoResponse:
    """Return summary metadata regarding loaded decision models and validation metrics."""
    pred = _get_predictor()
    meta_path = settings.artifacts_dir / "metadata" / "model_metadata.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Model metadata not found.")
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    reg_raw = meta.get("model_registry", [])
    registry_items = [ModelRegistryItem(**item) for item in reg_raw] if reg_raw else []

    classes = (
        [str(c) for c in pred._decision_clf.classes_]
        if (pred and hasattr(pred, "_decision_clf") and pred._decision_clf is not None)
        else ["NORMAL", "GENUINE_EXTREME", "SENSOR_FAULT"]
    )

    return ModelInfoResponse(
        model_version=meta.get("model_version", "unknown"),
        decision_model=meta.get("decision_model", "unknown"),
        val_macro_f1=float(meta.get("val_macro_f1", 0.0)),
        train_date=meta.get("train_date", "unknown"),
        classes=classes,
        model_registry=registry_items,
    )


@app.get("/model-registry", response_model=ModelRegistryResponse)
async def get_model_registry() -> ModelRegistryResponse:
    """Return the complete multi-model registry with validation metrics and statuses."""
    meta_path = settings.artifacts_dir / "metadata" / "model_metadata.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Model metadata not found.")
    with open(meta_path, "r", encoding="utf-8") as f:
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
    mgr = _get_data_manager()
    raw_stations = mgr.get_stations()
    if not raw_stations:
        return StationListResponse(stations=[], total=0)

    records = []
    for s in raw_stations:
        rec_data = dict(s)
        if rec_data.get("anomaly_consensus") and isinstance(rec_data["anomaly_consensus"], dict):
            rec_data["anomaly_consensus"] = AnomalyConsensus(**rec_data["anomaly_consensus"])
        records.append(StationRecord(**rec_data))

    return StationListResponse(stations=records, total=len(records))


@app.get("/anomalies", response_model=AnomalyListResponse)
async def get_anomalies() -> AnomalyListResponse:
    """Return only anomalous observations (prediction != NORMAL) from latest per station."""
    mgr = _get_data_manager()
    raw_anomalies = mgr.get_anomalies()
    if not raw_anomalies:
        return AnomalyListResponse(anomalies=[], total=0, sensor_faults=0, genuine_events=0)

    records = []
    for a in raw_anomalies:
        rec_data = dict(a)
        if rec_data.get("anomaly_consensus") and isinstance(rec_data["anomaly_consensus"], dict):
            rec_data["anomaly_consensus"] = AnomalyConsensus(**rec_data["anomaly_consensus"])
        records.append(AnomalyRecord(**rec_data))

    sensor_faults = sum(1 for a in records if a.prediction == "SENSOR_FAULT")
    genuine_events = sum(1 for a in records if a.prediction == "GENUINE_EXTREME")

    return AnomalyListResponse(
        anomalies=records,
        total=len(records),
        sensor_faults=sensor_faults,
        genuine_events=genuine_events,
    )


@app.get("/stations/{station_id}/history", response_model=HistoryResponse)
async def get_station_history(station_id: str) -> HistoryResponse:
    """Return chronological observations for a specific station from persistent store."""
    mgr = _get_data_manager()
    raw_history = mgr.get_station_history(station_id, limit=200)
    if not raw_history:
        # Check if station exists in station cache
        stations = mgr.get_stations()
        matching = [s for s in stations if s["station_id"] == station_id]
        if not matching:
            raise HTTPException(status_code=404, detail=f"Station '{station_id}' not found.")
        # If station exists with single observation
        s = matching[0]
        raw_history = [{
            "timestamp": s["latest_timestamp"],
            "temperature_c": s["temperature_c"],
            "relative_humidity_pct": s["relative_humidity_pct"],
            "pressure_hpa": s["pressure_hpa"],
            "wind_speed_kmh": s["wind_speed_kmh"],
            "rainfall_mm": s["rainfall_mm"],
            "ground_truth_label": None,
            "fault_description": None,
        }]

    records = [HistoryRecord(**r) for r in raw_history]
    return HistoryResponse(
        station_id=station_id,
        records=records,
        total=len(records),
    )


@app.get("/data-source/status")
async def get_data_source_status() -> dict:
    """Return live data source status, telemetry diagnostics, and historical store metrics."""
    mgr = _get_data_manager()
    return mgr.get_status()


# ── Historical Data & Chart Endpoints ──────────────────────────────────────────

@app.get("/historical/status", response_model=HistoricalStatusResponse)
async def get_historical_status() -> HistoricalStatusResponse:
    """Return historical database store statistics, coverage dates, and records count."""
    store = _get_historical_store()
    status_data = store.get_status()
    status_data["target_historical_years"] = settings.historical_years
    return HistoricalStatusResponse(**status_data)


@app.get("/historical/stations/{station_id}", response_model=AdaptiveHistoryResponse)
async def get_historical_station_telemetry(
    station_id: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    metric: Optional[str] = None,
    max_points: int = 200,
) -> AdaptiveHistoryResponse:
    """Return adaptive time-aware telemetry points and anomaly markers across 10-15 year ranges."""
    store = _get_historical_store()
    res = store.get_station_history_adaptive(
        station_id=station_id,
        start=start,
        end=end,
        metric=metric,
        max_points=max_points,
    )
    if res["total_records"] == 0:
        # Fallback to in-memory live station cache if DB has not yet accumulated multi-year data
        mgr = _get_data_manager()
        cached_history = mgr.get_station_history(station_id, limit=max_points)
        if cached_history:
            res["total_records"] = len(cached_history)
            res["displayed_points"] = len(cached_history)
            res["points"] = cached_history
            res["latest_observation"] = cached_history[-1]

    return AdaptiveHistoryResponse(**res)


@app.get("/historical/export")
async def export_historical_telemetry(
    start: Optional[str] = None,
    end: Optional[str] = None,
    station_id: Optional[str] = None,
    format: str = "xlsx",
):
    """Download filtered historical observations as partitioned Excel (.xlsx) or CSV."""
    exporter = _get_historical_exporter()
    buf, filename, media_type = exporter.export_data_buffer(
        start=start,
        end=end,
        station_id=station_id,
        export_format=format,
    )
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Access-Control-Expose-Headers": "Content-Disposition",
    }
    return StreamingResponse(buf, media_type=media_type, headers=headers)


# ── Continuous Model Training Endpoints ────────────────────────────────────────

@app.post("/training/start", response_model=TrainingStartResponse)
async def start_training(req: Optional[TrainingStartRequest] = None) -> TrainingStartResponse:
    """Trigger background continuous model training workflow using historical AWS observations."""
    mgr = _get_training_manager()
    start_d = req.start_date if req else None
    end_d = req.end_date if req else None
    train_r = req.train_ratio if req and req.train_ratio else 0.70
    val_r = req.val_ratio if req and req.val_ratio else 0.15

    training_id = mgr.start_training_job(
        start_date=start_d,
        end_date=end_d,
        train_ratio=train_r,
        val_ratio=val_r,
    )
    return TrainingStartResponse(
        status="started",
        training_id=training_id,
        message=f"Continuous model training job {training_id} started in background.",
    )


@app.get("/training/status", response_model=TrainingStatusResponse)
async def get_training_status(training_id: Optional[str] = None) -> TrainingStatusResponse:
    """Return status and progress of active or specified training job."""
    mgr = _get_training_manager()
    info = mgr.get_status(training_id=training_id)
    return TrainingStatusResponse(**info)


@app.get("/training/history", response_model=TrainingHistoryResponse)
async def get_training_history(limit: int = 20) -> TrainingHistoryResponse:
    """Return previous continuous model training runs."""
    mgr = _get_training_manager()
    runs = mgr.get_history(limit=limit)
    return TrainingHistoryResponse(runs=runs, total=len(runs))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)

