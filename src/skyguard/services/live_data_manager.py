"""Live AWS Data Manager for SkyGuard AI.

Orchestrates live IMD data polling, station observation buffers, feature caching,
fault intelligence inference, and station telemetry routing.
Ensures zero synthetic fallback when DATA_SOURCE=imd.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from skyguard.config.settings import settings
from skyguard.data.loader import load_raw
from skyguard.inference.predictor import SkyGuardPredictor
from skyguard.services.historical_exporter import HistoricalExporter
from skyguard.services.historical_store import HistoricalStore
from skyguard.services.imd_client import IMDClient
from skyguard.services.imd_normalizer import IMDNormalizer

logger = logging.getLogger("skyguard.services.live_data_manager")


class LiveDataManager:
    """Central orchestration manager for live AWS observations and prediction caches."""

    def __init__(
        self,
        predictor: Optional[SkyGuardPredictor] = None,
        imd_client: Optional[IMDClient] = None,
        store: Optional[HistoricalStore] = None,
        exporter: Optional[HistoricalExporter] = None,
        data_source: Optional[str] = None,
        max_history_per_station: int = 100,
    ) -> None:
        self.predictor = predictor
        self.imd_client = imd_client or IMDClient()
        self.store = store or HistoricalStore()
        self.exporter = exporter or HistoricalExporter(store=self.store)
        self.data_source = (data_source or settings.data_source).lower().strip()
        self.max_history = max_history_per_station

        # Historical observations buffer: station_id -> list of normalized observation dicts
        self._station_history: dict[str, list[dict[str, Any]]] = defaultdict(list)

        # In-memory inference caches for ultra-fast API response times
        self._station_cache: list[dict[str, Any]] = []
        self._anomaly_cache: list[dict[str, Any]] = []

        # State tracking
        self._total_live_observations = 0
        self._last_successful_fetch: Optional[datetime] = None
        self._latest_observation_timestamp: Optional[str] = None
        self._last_error: Optional[str] = None
        self._is_polling = False
        self._poll_task: Optional[asyncio.Task] = None

    def initialize(self) -> None:
        """Initialize data manager on application startup."""
        logger.info("[SkyGuard] Initializing LiveDataManager (Active Source: %s)", self.data_source.upper())

        if self.data_source == "synthetic":
            logger.info("[SkyGuard] DATA_SOURCE=synthetic configured explicitly. Loading test dataset.")
            self._load_synthetic_dataset()
        else:
            # Live IMD data mode — strictly live data only, zero synthetic fallback
            logger.info("[SkyGuard] DATA_SOURCE=imd active. Querying IMD live AWS stream...")
            self.fetch_and_update()

    def _load_synthetic_dataset(self) -> None:
        """Load synthetic historical dataset from CSV ONLY when explicitly configured."""
        try:
            path = settings.raw_data_path
            df = load_raw(path)
            logger.info("[SkyGuard] Loaded synthetic dataset: %d rows, %d stations", len(df), df["station_id"].nunique())

            self._station_history.clear()
            for _, row in df.iterrows():
                obs = self._series_to_obs(row)
                self._station_history[obs["station_id"]].append(obs)

            self._recompute_caches_from_history()
            self._last_successful_fetch = datetime.now(timezone.utc)
            self._last_error = None
        except Exception as exc:
            logger.error("[SkyGuard] Failed to load synthetic dataset: %s", exc)
            self._last_error = str(exc)

    def fetch_and_update(self) -> bool:
        """Fetch latest live observations from IMD API, normalize, and update inference caches."""
        if self.data_source == "synthetic":
            self._load_synthetic_dataset()
            return True

        logger.info("[SkyGuard] Requesting live observations from IMD API...")
        raw_records, error_msg = self.imd_client.fetch_raw_observations()
        if error_msg or not raw_records:
            self._last_error = error_msg or "No observations returned by IMD API"
            logger.warning("[SkyGuard] Live IMD fetch failed: %s", self._last_error)
            return False

        normalized = IMDNormalizer.normalize_batch(raw_records)
        if not normalized:
            self._last_error = "Zero valid observations after normalization"
            logger.warning("[SkyGuard] %s", self._last_error)
            return False

        # Ingest normalized records into station history buffer
        for obs in normalized:
            stn = obs["station_id"]
            if not self._station_history[stn] or self._station_history[stn][-1]["timestamp"] != obs["timestamp"]:
                self._station_history[stn].append(obs)
                self._total_live_observations += 1
                if len(self._station_history[stn]) > self.max_history:
                    self._station_history[stn].pop(0)

        # Persist normalized records to persistent HistoricalStore
        try:
            self.store.insert_observations(normalized)
        except Exception as exc:
            logger.warning("[SkyGuard] Failed to persist live records to HistoricalStore: %s", exc)

        # Sync current year Excel partition
        try:
            self.exporter.sync_live_observations_to_current_partition(normalized)
        except Exception as exc:
            logger.debug("[SkyGuard] Excel partition sync error: %s", exc)

        self._latest_observation_timestamp = normalized[-1]["timestamp"]
        self._recompute_caches_from_history()
        self._last_successful_fetch = datetime.now(timezone.utc)
        self._last_error = None
        logger.info("[SkyGuard] Successfully updated live stream: %d stations, %d total observations.", len(self._station_cache), self._total_live_observations)
        return True

    def ingest_live_observations(self, normalized_records: list[dict[str, Any]]) -> None:
        """Directly inject normalized observations into the live pipeline (e.g. from webhook or push stream)."""
        if not normalized_records:
            return

        for obs in normalized_records:
            stn = obs["station_id"]
            if not self._station_history[stn] or self._station_history[stn][-1]["timestamp"] != obs["timestamp"]:
                self._station_history[stn].append(obs)
                self._total_live_observations += 1
                if len(self._station_history[stn]) > self.max_history:
                    self._station_history[stn].pop(0)

        # Persist to HistoricalStore
        try:
            self.store.insert_observations(normalized_records)
        except Exception as exc:
            logger.warning("[SkyGuard] Failed to persist injected records to HistoricalStore: %s", exc)

        self._latest_observation_timestamp = normalized_records[-1]["timestamp"]
        self._recompute_caches_from_history()
        self._last_successful_fetch = datetime.now(timezone.utc)
        self._last_error = None

    def _recompute_caches_from_history(self) -> None:
        """Run ML predictor on the latest observation for every station and update caches."""
        if not self.predictor:
            return

        latest_obs_list: list[dict[str, Any]] = []
        for station_id, history in self._station_history.items():
            if history:
                latest_obs_list.append(history[-1])

        if not latest_obs_list:
            self._station_cache = []
            self._anomaly_cache = []
            return

        # Run high-performance batch prediction if supported, or per-station single prediction
        if hasattr(self.predictor, "predict_batch"):
            try:
                inferences = self.predictor.predict_batch(latest_obs_list)
            except Exception as exc:
                logger.warning("[SkyGuard] Predictor batch error: %s. Falling back to single inference.", exc)
                inferences = []
                for obs in latest_obs_list:
                    try:
                        inferences.append(self.predictor.predict_single(obs))
                    except Exception:
                        inferences.append(self._default_inference_fallback())
        else:
            inferences = []
            for obs in latest_obs_list:
                try:
                    inferences.append(self.predictor.predict_single(obs))
                except Exception:
                    inferences.append(self._default_inference_fallback())

        station_records: list[dict[str, Any]] = []
        anomaly_records: list[dict[str, Any]] = []

        for latest_obs, inf in zip(latest_obs_list, inferences):
            rec = {
                "station_id": str(latest_obs["station_id"]),
                "station_name": str(latest_obs.get("station_name", "")) or None,
                "latitude": float(latest_obs["latitude"]),
                "longitude": float(latest_obs["longitude"]),
                "latest_timestamp": str(latest_obs["timestamp"]),
                "temperature_c": float(latest_obs["temperature_c"]),
                "relative_humidity_pct": float(latest_obs["relative_humidity_pct"]),
                "pressure_hpa": float(latest_obs["pressure_hpa"]),
                "wind_speed_kmh": float(latest_obs.get("wind_speed_kmh", 0.0)),
                "rainfall_mm": float(latest_obs.get("rainfall_mm", 0.0)),
                "prediction": inf["prediction"],
                "confidence": inf["confidence"],
                "confidence_level": inf.get("confidence_level", "MEDIUM"),
                "uncertainty_score": inf.get("uncertainty_score", 0.0),
                "anomaly_score": inf["anomaly_score"],
                "anomaly_consensus": inf.get("anomaly_consensus"),
                "model_agreement": inf.get("model_agreement", 1.0),
                "model_coverage": inf.get("model_coverage", "6/6 active"),
                "fault_type": inf["fault_type"],
                "fault_confidence": inf.get("fault_confidence", 0.0),
                "fault_evidence": inf.get("fault_evidence", []),
                "genuine_event_score": inf.get("genuine_event_score", 0.0),
                "genuine_event_evidence": inf.get("genuine_event_evidence", []),
                "severity": inf["severity"],
                "sensor_health": inf["sensor_health"],
                "sensor_health_status": inf["sensor_health_status"],
                "expected_values": inf["expected_values"],
                "observed_values": inf["observed_values"],
                "top_reasons": inf["top_reasons"],
                "recommended_action": inf.get("recommended_action"),
                "correction": inf["correction"],
            }
            station_records.append(rec)

            if inf["prediction"] != "NORMAL":
                anomaly_records.append({
                    "station_id": rec["station_id"],
                    "station_name": rec["station_name"],
                    "latitude": rec["latitude"],
                    "longitude": rec["longitude"],
                    "timestamp": rec["latest_timestamp"],
                    "prediction": rec["prediction"],
                    "confidence": rec["confidence"],
                    "confidence_level": rec["confidence_level"],
                    "uncertainty_score": rec["uncertainty_score"],
                    "anomaly_score": rec["anomaly_score"],
                    "anomaly_consensus": rec["anomaly_consensus"],
                    "model_agreement": rec["model_agreement"],
                    "fault_type": rec["fault_type"],
                    "fault_confidence": rec["fault_confidence"],
                    "fault_evidence": rec["fault_evidence"],
                    "genuine_event_score": rec["genuine_event_score"],
                    "genuine_event_evidence": rec["genuine_event_evidence"],
                    "severity": rec["severity"],
                    "sensor_health": rec["sensor_health"],
                    "sensor_health_status": rec["sensor_health_status"],
                    "expected_values": rec["expected_values"],
                    "observed_values": rec["observed_values"],
                    "top_reasons": rec["top_reasons"],
                    "recommended_action": rec["recommended_action"],
                    "correction": rec["correction"],
                })

        self._station_cache = station_records
        self._anomaly_cache = anomaly_records

    def get_stations(self) -> list[dict[str, Any]]:
        """Return cached latest observations and predictions for all stations."""
        return self._station_cache

    def get_anomalies(self) -> list[dict[str, Any]]:
        """Return cached anomalous station observations."""
        return self._anomaly_cache

    def get_station_history(self, station_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Return chronological observation history for a specific station from persistent store."""
        db_records = self.store.get_observations(station_id=station_id, limit=limit)
        if db_records:
            return db_records

        history = self._station_history.get(station_id, [])
        if not history:
            return []

        recent = history[-limit:]
        records = []
        for obs in recent:
            records.append({
                "timestamp": str(obs["timestamp"]),
                "temperature_c": float(obs["temperature_c"]),
                "relative_humidity_pct": float(obs["relative_humidity_pct"]),
                "pressure_hpa": float(obs["pressure_hpa"]),
                "wind_speed_kmh": float(obs.get("wind_speed_kmh", 0.0)),
                "rainfall_mm": float(obs.get("rainfall_mm", 0.0)),
                "ground_truth_label": obs.get("ground_truth_label"),
                "fault_description": obs.get("fault_description"),
            })
        return records

    def get_status(self) -> dict[str, Any]:
        """Return live ingestion status, diagnostics, and persistent historical metrics."""
        return {
            "data_source": self.data_source,
            "configured_data_source": self.data_source,
            "real_data_source": "IMD Live AWS API" if self.data_source == "imd" else "Synthetic Dataset",
            "is_live": self.data_source == "imd" and len(self._station_cache) > 0 and self._last_error is None,
            "live_observations_received": self._total_live_observations,
            "live_stations_monitored": len(self._station_cache),
            "stations_monitored": len(self._station_cache),
            "anomalies_detected": len(self._anomaly_cache),
            "last_successful_update": self._last_successful_fetch.isoformat() if self._last_successful_fetch else None,
            "latest_observation_timestamp": self._latest_observation_timestamp,
            "polling_active": self._is_polling,
            "last_error": self._last_error,
            "client_diagnostics": self.imd_client.get_diagnostics() if self.data_source == "imd" else None,
            "historical_store": self.store.get_status(),
        }

    async def start_polling(self, interval_seconds: Optional[int] = None) -> None:
        """Start asynchronous background polling loop."""
        interval = interval_seconds or settings.imd_poll_interval_seconds
        self._is_polling = True
        logger.info("[SkyGuard] Background live data polling started (interval=%ds)", interval)

        while self._is_polling:
            try:
                await asyncio.sleep(interval)
                logger.debug("[SkyGuard] Executing scheduled live data polling...")
                await asyncio.to_thread(self.fetch_and_update)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("[SkyGuard] Error in background polling loop: %s", exc)

    def stop_polling(self) -> None:
        """Stop background polling loop."""
        self._is_polling = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()

    @staticmethod
    def _series_to_obs(row: pd.Series) -> dict[str, Any]:
        """Convert a dataframe row series to a standardized observation dict."""
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
            "ground_truth_label": str(row.get("ground_truth_label", "")) if pd.notna(row.get("ground_truth_label")) else None,
            "fault_description": str(row.get("fault_description", "")) if pd.notna(row.get("fault_description")) else None,
        }

    @staticmethod
    def _default_inference_fallback() -> dict[str, Any]:
        """Return safe fallback inference dictionary if predictor fails on a single observation."""
        return {
            "prediction": "UNKNOWN",
            "confidence": 0.0,
            "confidence_level": "LOW",
            "uncertainty_score": 0.5,
            "anomaly_score": 0.0,
            "anomaly_consensus": None,
            "model_agreement": 1.0,
            "model_coverage": "0/6 active",
            "fault_type": "NONE",
            "fault_confidence": 0.0,
            "fault_evidence": [],
            "genuine_event_score": 0.0,
            "genuine_event_evidence": [],
            "severity": "LOW",
            "sensor_health": 100.0,
            "sensor_health_status": "UNKNOWN",
            "expected_values": {},
            "observed_values": {},
            "top_reasons": [],
            "recommended_action": None,
            "correction": {},
        }
