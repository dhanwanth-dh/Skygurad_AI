"""FastAPI Backend Server for SkyGuard Multi-Model Intelligence Engine.

Re-exports the core application from `api.main` to ensure backwards compatibility
across both `api.main:app` and `skyguard.api.main:app` import paths.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel, Field

# Ensure project root is in sys.path
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from api.main import (
    app,
    get_model_registry,
    get_stations,
    get_anomalies,
    get_station_history,
    health,
    model_info,
    predict,
    _get_predictor,
    _get_dataset,
)
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

class ObservationRequest(BaseModel):
    station_id: str = Field(..., examples=["AWS_TN_01"])
    station_name: str | None = Field(None, examples=["Chennai Coastal AWS"])
    latitude: float = Field(..., examples=[13.0827])
    longitude: float = Field(..., examples=[80.2707])
    timestamp: str | None = Field(None, examples=["2025-02-15 14:00:00"])
    temperature_c: float = Field(..., examples=[32.5])
    relative_humidity_pct: float = Field(..., examples=[65.0])
    pressure_hpa: float = Field(..., examples=[1009.5])
    wind_speed_kmh: float = Field(..., examples=[14.2])
    rainfall_mm: float = Field(..., examples=[0.0])

__all__ = [
    "app",
    "get_model_registry",
    "get_stations",
    "get_anomalies",
    "get_station_history",
    "health",
    "model_info",
    "predict",
    "WeatherObservation",
    "PredictionResponse",
    "HealthResponse",
    "ModelInfoResponse",
    "ModelRegistryResponse",
    "StationListResponse",
    "AnomalyListResponse",
    "HistoryResponse",
    "ObservationRequest",
]

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("skyguard.api.main:app", host="0.0.0.0", port=port, reload=True)
