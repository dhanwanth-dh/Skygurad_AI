"""Historical Dataset Builder for SkyGuard AI Continuous Model Training.

Audits data quality, computes missing/duplicate metrics, applies preprocessing,
and performs strictly chronological train/val/test splitting with zero future data leakage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd

from skyguard.config.settings import settings
from skyguard.data.loader import load_raw
from skyguard.data.splitter import chronological_split
from skyguard.preprocessing.pipeline import run_preprocessing
from skyguard.services.historical_store import HistoricalStore

logger = logging.getLogger("skyguard.training.dataset_builder")


@dataclass
class DatasetAuditReport:
    """Comprehensive historical data quality and integrity report."""
    total_records: int
    unique_stations: int
    oldest_timestamp: Optional[str]
    latest_timestamp: Optional[str]
    missing_pct: dict[str, float]
    duplicate_records: int
    duplicate_rate_pct: float
    physical_bound_violations: int
    temporal_coverage_years: float


class HistoricalDatasetBuilder:
    """Loads historical observations, audits quality, and creates chronological training splits."""

    def __init__(self, store: Optional[HistoricalStore] = None) -> None:
        self.store = store or HistoricalStore()

    def load_dataset(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        station_ids: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """Load dataset from persistent HistoricalStore, or fallback to raw CSV if store is empty."""
        df = self.store.get_dataframe(start=start, end=end, station_ids=station_ids)
        if df.empty:
            logger.info("[DatasetBuilder] Historical store empty. Loading baseline training data from %s", settings.raw_data_path)
            df = load_raw(settings.raw_data_path)

        # Ensure timestamp is datetime and sorted chronologically
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df

    def audit_dataset(self, df: pd.DataFrame) -> DatasetAuditReport:
        """Calculate real data quality metrics across all historical observations."""
        total = len(df)
        if total == 0:
            return DatasetAuditReport(
                total_records=0,
                unique_stations=0,
                oldest_timestamp=None,
                latest_timestamp=None,
                missing_pct={},
                duplicate_records=0,
                duplicate_rate_pct=0.0,
                physical_bound_violations=0,
                temporal_coverage_years=0.0,
            )

        stns = int(df["station_id"].nunique())
        oldest = str(df["timestamp"].min())
        latest = str(df["timestamp"].max())

        # Missing percentages
        sensor_cols = ["temperature_c", "relative_humidity_pct", "pressure_hpa", "wind_speed_kmh", "rainfall_mm"]
        missing_pct = {
            col: round(float(df[col].isna().mean() * 100.0), 2)
            for col in sensor_cols if col in df.columns
        }

        # Duplicates on (station_id, timestamp)
        dup_mask = df.duplicated(subset=["station_id", "timestamp"], keep=False)
        dup_count = int(dup_mask.sum())
        dup_rate = round(float((dup_count / total) * 100.0), 3)

        # Physical bound violations
        violations = 0
        bounds = settings.physical_bounds
        for col, (b_min, b_max) in bounds.items():
            if col in df.columns:
                out_of_bounds = (df[col] < b_min) | (df[col] > b_max)
                violations += int(out_of_bounds.sum())

        dt_old = df["timestamp"].min()
        dt_new = df["timestamp"].max()
        years = round((dt_new - dt_old).days / 365.25, 2)

        return DatasetAuditReport(
            total_records=total,
            unique_stations=stns,
            oldest_timestamp=oldest,
            latest_timestamp=latest,
            missing_pct=missing_pct,
            duplicate_records=dup_count,
            duplicate_rate_pct=dup_rate,
            physical_bound_violations=violations,
            temporal_coverage_years=years,
        )

    def prepare_training_splits(
        self,
        df: pd.DataFrame,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, DatasetAuditReport]:
        """Audit dataset, apply physical preprocessing, and perform strict chronological split."""
        audit = self.audit_dataset(df)
        logger.info(
            "[DatasetBuilder] Audit: %d records, %d stations, coverage: %s to %s (%.1f years)",
            audit.total_records,
            audit.unique_stations,
            audit.oldest_timestamp,
            audit.latest_timestamp,
            audit.temporal_coverage_years,
        )

        # Preprocessing & range validation
        df_proc = run_preprocessing(df)

        # Chronological Split (Strictly temporal order, NO random shuffling)
        split_result = chronological_split(
            df_proc,
            train_frac=train_ratio,
            val_frac=val_ratio,
        )

        train_df, val_df, test_df = split_result.train, split_result.val, split_result.test
        logger.info(
            "[DatasetBuilder] Chronological split complete: Train=%d, Val=%d, Test=%d (Zero future leakage)",
            len(train_df),
            len(val_df),
            len(test_df),
        )
        return train_df, val_df, test_df, audit
