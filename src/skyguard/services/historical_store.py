"""Persistent Historical AWS Data Store for SkyGuard AI.

Provides resilient SQLite storage (with PostgreSQL-compatible schema and migration readiness)
for 10-15 years of AWS observations, dynamic station metadata, training runs, and adaptive
chart downsampling queries.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from skyguard.config.settings import settings

logger = logging.getLogger("skyguard.services.historical_store")


class HistoricalStore:
    """Primary persistent data store for historical and live AWS observations."""

    def __init__(self, db_path: Optional[Path | str] = None) -> None:
        self.db_path = Path(db_path or settings.historical_db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a connection with WAL mode and row factory for concurrency."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_db(self) -> None:
        """Initialize database tables, unique constraints, and indexes."""
        with self._get_connection() as conn:
            # 1. Canonical AWS Observations Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS aws_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    station_id TEXT NOT NULL,
                    station_name TEXT,
                    district TEXT,
                    state TEXT,
                    latitude REAL,
                    longitude REAL,
                    temperature_c REAL,
                    relative_humidity_pct REAL,
                    pressure_hpa REAL,
                    wind_speed_kmh REAL,
                    rainfall_mm REAL,
                    ground_truth_label TEXT,
                    fault_description TEXT,
                    source TEXT DEFAULT 'imd',
                    ingested_at TEXT NOT NULL,
                    UNIQUE(station_id, timestamp)
                );
            """)

            # Multi-column indexes for fast temporal and station queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_stn_ts ON aws_observations (station_id, timestamp);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON aws_observations (timestamp);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_stn ON aws_observations (station_id);")

            # 2. Historical Ingestion Metadata Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS historical_ingestion_metadata (
                    station_id TEXT PRIMARY KEY,
                    station_name TEXT,
                    district TEXT,
                    state TEXT,
                    latitude REAL,
                    longitude REAL,
                    oldest_timestamp TEXT,
                    latest_timestamp TEXT,
                    last_sync TEXT,
                    records INTEGER DEFAULT 0
                );
            """)

            # 3. Model Training Runs History
            conn.execute("""
                CREATE TABLE IF NOT EXISTS training_runs (
                    training_id TEXT PRIMARY KEY,
                    model_version TEXT,
                    status TEXT,
                    progress REAL DEFAULT 0.0,
                    records_processed INTEGER DEFAULT 0,
                    stations INTEGER DEFAULT 0,
                    current_stage TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    metrics_json TEXT,
                    error TEXT
                );
            """)

            conn.commit()
            logger.debug("[HistoricalStore] Initialized database at %s", self.db_path)

    def insert_observations(self, records: list[dict[str, Any]]) -> int:
        """Insert a batch of normalized observations with automatic duplicate prevention.

        Returns the number of newly inserted records.
        """
        if not records:
            return 0

        now_iso = datetime.now(timezone.utc).isoformat()
        insert_rows = []

        for r in records:
            stn_id = str(r.get("station_id", "")).strip()
            ts = str(r.get("timestamp", "")).strip()
            if not stn_id or not ts:
                continue

            insert_rows.append((
                ts,
                stn_id,
                r.get("station_name"),
                r.get("district"),
                r.get("state"),
                float(r["latitude"]) if r.get("latitude") is not None and not pd.isna(r["latitude"]) else None,
                float(r["longitude"]) if r.get("longitude") is not None and not pd.isna(r["longitude"]) else None,
                float(r["temperature_c"]) if r.get("temperature_c") is not None and not pd.isna(r["temperature_c"]) else None,
                float(r["relative_humidity_pct"]) if r.get("relative_humidity_pct") is not None and not pd.isna(r["relative_humidity_pct"]) else None,
                float(r["pressure_hpa"]) if r.get("pressure_hpa") is not None and not pd.isna(r["pressure_hpa"]) else None,
                float(r.get("wind_speed_kmh", 0.0)) if r.get("wind_speed_kmh") is not None and not pd.isna(r.get("wind_speed_kmh")) else 0.0,
                float(r.get("rainfall_mm", 0.0)) if r.get("rainfall_mm") is not None and not pd.isna(r.get("rainfall_mm")) else 0.0,
                r.get("ground_truth_label"),
                r.get("fault_description"),
                r.get("source", "imd"),
                now_iso,
            ))

        if not insert_rows:
            return 0

        query = """
            INSERT OR IGNORE INTO aws_observations (
                timestamp, station_id, station_name, district, state,
                latitude, longitude, temperature_c, relative_humidity_pct,
                pressure_hpa, wind_speed_kmh, rainfall_mm,
                ground_truth_label, fault_description, source, ingested_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """

        inserted_count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            initial_changes = conn.total_changes
            cursor.executemany(query, insert_rows)
            inserted_count = conn.total_changes - initial_changes

            # Update metadata per station
            stn_ids = list({r[1] for r in insert_rows})
            for stn_id in stn_ids:
                meta_row = cursor.execute("""
                    SELECT MIN(timestamp) as oldest_ts, MAX(timestamp) as latest_ts,
                           COUNT(*) as total_records,
                           station_name, district, state, latitude, longitude
                    FROM aws_observations
                    WHERE station_id = ?
                """, (stn_id,)).fetchone()

                if meta_row and meta_row["total_records"] > 0:
                    cursor.execute("""
                        INSERT INTO historical_ingestion_metadata (
                            station_id, station_name, district, state,
                            latitude, longitude, oldest_timestamp,
                            latest_timestamp, last_sync, records
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(station_id) DO UPDATE SET
                            station_name = COALESCE(excluded.station_name, historical_ingestion_metadata.station_name),
                            district = COALESCE(excluded.district, historical_ingestion_metadata.district),
                            state = COALESCE(excluded.state, historical_ingestion_metadata.state),
                            latitude = COALESCE(excluded.latitude, historical_ingestion_metadata.latitude),
                            longitude = COALESCE(excluded.longitude, historical_ingestion_metadata.longitude),
                            oldest_timestamp = excluded.oldest_timestamp,
                            latest_timestamp = excluded.latest_timestamp,
                            last_sync = excluded.last_sync,
                            records = excluded.records;
                    """, (
                        stn_id,
                        meta_row["station_name"],
                        meta_row["district"],
                        meta_row["state"],
                        meta_row["latitude"],
                        meta_row["longitude"],
                        meta_row["oldest_ts"],
                        meta_row["latest_ts"],
                        now_iso,
                        meta_row["total_records"],
                    ))

            conn.commit()

        logger.debug("[HistoricalStore] Batch insert: %d rows received, %d new rows stored", len(records), inserted_count)
        return inserted_count

    def get_observations(
        self,
        station_id: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Retrieve chronological observations with optional filtering."""
        clauses = []
        params: list[Any] = []

        if station_id:
            clauses.append("station_id = ?")
            params.append(station_id)
        if start:
            clauses.append("timestamp >= ?")
            params.append(start)
        if end:
            clauses.append("timestamp <= ?")
            params.append(end)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit_sql = f"LIMIT {int(limit)}" if limit else ""

        sql = f"""
            SELECT timestamp, station_id, station_name, district, state,
                   latitude, longitude, temperature_c, relative_humidity_pct,
                   pressure_hpa, wind_speed_kmh, rainfall_mm,
                   ground_truth_label, fault_description, source
            FROM aws_observations
            {where_sql}
            ORDER BY timestamp ASC
            {limit_sql};
        """

        with self._get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def get_station_history_adaptive(
        self,
        station_id: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        metric: Optional[str] = None,
        max_points: int = 200,
    ) -> dict[str, Any]:
        """Perform adaptive time-aware aggregation for smooth charting across 15-year spans."""
        observations = self.get_observations(station_id=station_id, start=start, end=end)
        if not observations:
            return {
                "station_id": station_id,
                "total_records": 0,
                "displayed_points": 0,
                "points": [],
                "anomalies": [],
                "latest_observation": None,
            }

        total_records = len(observations)
        latest_obs = observations[-1]

        # If data points are below max_points, return raw points directly
        if total_records <= max_points:
            points = observations
        else:
            # Adaptive bucketed aggregation
            df = pd.DataFrame(observations)
            df["dt"] = pd.to_datetime(df["timestamp"])
            step = max(1, total_records // max_points)
            sampled_indices = list(range(0, total_records, step))
            if (total_records - 1) not in sampled_indices:
                sampled_indices.append(total_records - 1)
            points = df.iloc[sampled_indices].to_dict(orient="records")

        # Anomaly markers
        anomalies = [
            p for p in observations
            if p.get("ground_truth_label") and p["ground_truth_label"] != "NORMAL"
        ]

        return {
            "station_id": station_id,
            "total_records": total_records,
            "displayed_points": len(points),
            "points": points,
            "anomalies": anomalies,
            "latest_observation": latest_obs,
        }

    def get_status(self) -> dict[str, Any]:
        """Return comprehensive storage, record count, and temporal coverage status."""
        with self._get_connection() as conn:
            total_obs = conn.execute("SELECT COUNT(*) FROM aws_observations").fetchone()[0]
            total_stns = conn.execute("SELECT COUNT(DISTINCT station_id) FROM aws_observations").fetchone()[0]
            bounds = conn.execute("SELECT MIN(timestamp), MAX(timestamp) FROM aws_observations").fetchone()
            last_sync_row = conn.execute("SELECT MAX(last_sync) FROM historical_ingestion_metadata").fetchone()

        oldest_ts = bounds[0] if bounds and bounds[0] else None
        latest_ts = bounds[1] if bounds and bounds[1] else None
        last_sync = last_sync_row[0] if last_sync_row and last_sync_row[0] else None

        years_available = 0.0
        if oldest_ts and latest_ts:
            try:
                dt_old = datetime.fromisoformat(oldest_ts.replace(" ", "T"))
                dt_new = datetime.fromisoformat(latest_ts.replace(" ", "T"))
                years_available = round((dt_new - dt_old).days / 365.25, 2)
            except Exception:
                pass

        return {
            "available": total_obs > 0,
            "stations": total_stns,
            "records": total_obs,
            "oldest_observation": oldest_ts,
            "latest_observation": latest_ts,
            "years_available": years_available,
            "last_sync": last_sync,
            "db_path": str(self.db_path),
        }

    def get_station_registry(self) -> list[dict[str, Any]]:
        """Return station registry with temporal lifecycle bounds."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT station_id, station_name, district, state,
                       latitude, longitude, oldest_timestamp, latest_timestamp,
                       last_sync, records
                FROM historical_ingestion_metadata
                ORDER BY station_id ASC
            """).fetchall()
            return [dict(r) for r in rows]

    def get_dataframe(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        station_ids: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """Load observations into a pandas DataFrame for ML training."""
        clauses = []
        params: list[Any] = []

        if start:
            clauses.append("timestamp >= ?")
            params.append(start)
        if end:
            clauses.append("timestamp <= ?")
            params.append(end)
        if station_ids:
            placeholders = ",".join("?" * len(station_ids))
            clauses.append(f"station_id IN ({placeholders})")
            params.extend(station_ids)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT timestamp, station_id, station_name, district, state,
                   latitude, longitude, temperature_c, relative_humidity_pct,
                   pressure_hpa, wind_speed_kmh, rainfall_mm,
                   ground_truth_label, fault_description
            FROM aws_observations
            {where_sql}
            ORDER BY timestamp ASC;
        """

        with self._get_connection() as conn:
            df = pd.read_sql_query(sql, conn, params=params)

        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df

    # ── Training Run Lifecycle Tracking ────────────────────────────────────────

    def record_training_start(
        self,
        training_id: str,
        model_version: str,
        stations: int,
        records_processed: int,
    ) -> None:
        """Record the start of a training job."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO training_runs (
                    training_id, model_version, status, progress,
                    records_processed, stations, current_stage, started_at
                ) VALUES (?, ?, 'RUNNING', 0.0, ?, ?, 'INITIALIZING', ?);
            """, (training_id, model_version, records_processed, stations, now))
            conn.commit()

    def update_training_progress(
        self,
        training_id: str,
        progress: float,
        stage: str,
    ) -> None:
        """Update progress percentage and current stage of a running training job."""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE training_runs
                SET progress = ?, current_stage = ?
                WHERE training_id = ?;
            """, (progress, stage, training_id))
            conn.commit()

    def record_training_complete(
        self,
        training_id: str,
        metrics: dict[str, Any],
    ) -> None:
        """Record successful training completion."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE training_runs
                SET status = 'COMPLETED', progress = 100.0, current_stage = 'COMPLETED',
                    completed_at = ?, metrics_json = ?
                WHERE training_id = ?;
            """, (now, json.dumps(metrics), training_id))
            conn.commit()

    def record_training_failed(
        self,
        training_id: str,
        error_msg: str,
    ) -> None:
        """Record training failure."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE training_runs
                SET status = 'FAILED', current_stage = 'FAILED',
                    completed_at = ?, error = ?
                WHERE training_id = ?;
            """, (now, error_msg, training_id))
            conn.commit()

    def get_training_status(self, training_id: str) -> Optional[dict[str, Any]]:
        """Retrieve status of a specific training run."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM training_runs WHERE training_id = ?", (training_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            if res.get("metrics_json"):
                res["metrics"] = json.loads(res["metrics_json"])
            return res

    def get_training_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Retrieve historical training runs."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM training_runs
                ORDER BY started_at DESC
                LIMIT ?;
            """, (limit,)).fetchall()
            results = []
            for r in rows:
                item = dict(r)
                if item.get("metrics_json"):
                    item["metrics"] = json.loads(item["metrics_json"])
                results.append(item)
            return results
