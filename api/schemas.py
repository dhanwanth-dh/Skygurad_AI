"""Pydantic schemas for FastAPI request/response validation."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class WeatherObservation(BaseModel):
    timestamp: str
    station_id: str
    station_name: Optional[str] = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    temperature_c: float = Field(..., ge=-25, le=75)
    relative_humidity_pct: float = Field(..., ge=0, le=100)
    pressure_hpa: float = Field(..., ge=680, le=1084)
    wind_speed_kmh: float = Field(..., ge=0, le=200)
    rainfall_mm: float = Field(..., ge=0, le=500)


class AnomalyConsensus(BaseModel):
    models_agreeing: int = 0
    models_total: int = 6
    score: float = 0.0
    detector_scores: dict[str, float] = {}


class TraceStep(BaseModel):
    stage: str
    status: str
    score: Optional[float] = None
    confidence: Optional[float] = None
    uncertainty: Optional[float] = None
    summary: str
    evidence: Optional[list[str]] = None
    detector_scores: Optional[dict[str, float]] = None
    expected_values: Optional[dict[str, Optional[float]]] = None


class PredictionResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    station_id: str
    timestamp: str
    prediction: str
    confidence: float
    confidence_level: Optional[str] = "MEDIUM"
    uncertainty_score: Optional[float] = 0.0
    class_probabilities: dict[str, float]
    anomaly_score: float
    anomaly_consensus: Optional[AnomalyConsensus] = None
    model_agreement: Optional[float] = 1.0
    model_coverage: Optional[str] = "6/6 active"
    fault_type: str = "NONE"
    fault_confidence: Optional[float] = 0.0
    fault_evidence: Optional[list[str]] = []
    genuine_event_score: Optional[float] = 0.0
    genuine_event_evidence: Optional[list[str]] = []
    severity: str
    sensor_health: float
    sensor_health_status: str
    expected_values: dict[str, Optional[float]]
    observed_values: dict[str, float]
    top_reasons: list[str]
    recommended_action: Optional[str] = None
    correction: dict[str, Any] = {}
    enabled_models: Optional[list[str]] = []
    trace: Optional[list[TraceStep]] = []
    model_version: str


class HealthResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    status: str
    model_loaded: bool
    version: str


class ModelRegistryItem(BaseModel):
    model_config = {"protected_namespaces": ()}

    model_name: str
    category: str
    status: str
    weight: Optional[float] = None
    val_metric: Optional[str] = None


class ModelInfoResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    model_version: str
    decision_model: str
    val_macro_f1: float
    train_date: str
    classes: list[str]
    model_registry: Optional[list[ModelRegistryItem]] = []


class ModelRegistryResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    model_version: str
    train_date: str
    total_models: int
    active_models: int
    disabled_models: int
    registry: list[ModelRegistryItem]


# ── Station & Anomaly Schemas ──────────────────────────────────────────────────

class StationRecord(BaseModel):
    """One row per unique AWS station with its latest observation + inference."""
    model_config = {"protected_namespaces": ()}

    station_id: str
    station_name: Optional[str]
    latitude: float
    longitude: float
    latest_timestamp: str
    temperature_c: float
    relative_humidity_pct: float
    pressure_hpa: float
    wind_speed_kmh: float
    rainfall_mm: float
    # inference results for latest observation
    prediction: str
    confidence: float
    confidence_level: Optional[str] = "MEDIUM"
    uncertainty_score: Optional[float] = 0.0
    anomaly_score: float
    anomaly_consensus: Optional[AnomalyConsensus] = None
    model_agreement: Optional[float] = 1.0
    model_coverage: Optional[str] = "6/6 active"
    fault_type: str
    fault_confidence: Optional[float] = 0.0
    fault_evidence: Optional[list[str]] = []
    genuine_event_score: Optional[float] = 0.0
    genuine_event_evidence: Optional[list[str]] = []
    severity: str
    sensor_health: float
    sensor_health_status: str
    expected_values: dict[str, Optional[float]]
    observed_values: dict[str, float]
    top_reasons: list[str]
    recommended_action: Optional[str] = None
    correction: dict[str, Any]


class StationListResponse(BaseModel):
    stations: list[StationRecord]
    total: int


class AnomalyRecord(BaseModel):
    """An anomalous observation — prediction != NORMAL."""
    model_config = {"protected_namespaces": ()}

    station_id: str
    station_name: Optional[str]
    latitude: float
    longitude: float
    timestamp: str
    prediction: str
    confidence: float
    confidence_level: Optional[str] = "MEDIUM"
    uncertainty_score: Optional[float] = 0.0
    anomaly_score: float
    anomaly_consensus: Optional[AnomalyConsensus] = None
    model_agreement: Optional[float] = 1.0
    fault_type: str
    fault_confidence: Optional[float] = 0.0
    fault_evidence: Optional[list[str]] = []
    genuine_event_score: Optional[float] = 0.0
    genuine_event_evidence: Optional[list[str]] = []
    severity: str
    sensor_health: float
    sensor_health_status: str
    expected_values: dict[str, Optional[float]]
    observed_values: dict[str, float]
    top_reasons: list[str]
    recommended_action: Optional[str] = None
    correction: dict[str, Any]


class AnomalyListResponse(BaseModel):
    anomalies: list[AnomalyRecord]
    total: int
    sensor_faults: int
    genuine_events: int


class HistoryRecord(BaseModel):
    timestamp: str
    temperature_c: float
    relative_humidity_pct: float
    pressure_hpa: float
    wind_speed_kmh: float
    rainfall_mm: float
    ground_truth_label: Optional[str]
    fault_description: Optional[str]


class HistoryResponse(BaseModel):
    station_id: str
    records: list[HistoryRecord]
    total: int


# ── Historical & Continuous Training Schemas ───────────────────────────────────

class HistoricalStatusResponse(BaseModel):
    available: bool
    stations: int
    records: int
    oldest_observation: Optional[str] = None
    latest_observation: Optional[str] = None
    years_available: float = 0.0
    last_sync: Optional[str] = None
    target_historical_years: Optional[int] = 15
    db_path: Optional[str] = None


class AdaptiveHistoryPoint(BaseModel):
    timestamp: str
    temperature_c: Optional[float] = None
    relative_humidity_pct: Optional[float] = None
    pressure_hpa: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    rainfall_mm: Optional[float] = None
    ground_truth_label: Optional[str] = None
    fault_description: Optional[str] = None


class AdaptiveHistoryResponse(BaseModel):
    station_id: str
    total_records: int
    displayed_points: int
    points: list[dict[str, Any]]
    anomalies: list[dict[str, Any]]
    latest_observation: Optional[dict[str, Any]] = None


class TrainingStartRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    train_ratio: Optional[float] = 0.70
    val_ratio: Optional[float] = 0.15


class TrainingStartResponse(BaseModel):
    status: str
    training_id: str
    message: str


class TrainingStatusResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    training_id: Optional[str] = None
    model_version: Optional[str] = None
    status: str
    progress: float = 0.0
    records_processed: int = 0
    stations: int = 0
    current_stage: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    metrics: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class TrainingHistoryResponse(BaseModel):
    runs: list[dict[str, Any]]
    total: int

