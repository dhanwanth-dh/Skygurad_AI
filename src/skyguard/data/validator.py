"""Data validator — structural and physical checks, returns a quality report."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "timestamp", "station_id",
    "latitude", "longitude",
    "temperature_c", "relative_humidity_pct", "pressure_hpa",
    "wind_speed_kmh", "rainfall_mm",
]

PHYSICAL_BOUNDS: dict[str, tuple[float, float]] = {
    "temperature_c": (-20.0, 60.0),
    "relative_humidity_pct": (0.0, 100.0),
    "pressure_hpa": (700.0, 1084.0),
    "wind_speed_kmh": (0.0, 200.0),
    "rainfall_mm": (0.0, 500.0),
}


@dataclass
class ValidationReport:
    missing_columns: list[str] = field(default_factory=list)
    missing_values: dict[str, int] = field(default_factory=dict)
    duplicate_rows: int = 0
    duplicate_station_timestamps: int = 0
    physical_violations: dict[str, int] = field(default_factory=dict)
    timestamp_parse_failures: int = 0
    is_valid: bool = True
    warnings: list[str] = field(default_factory=list)

    def summarise(self) -> str:
        lines = ["=== Validation Report ==="]
        lines.append(f"Missing columns      : {self.missing_columns or 'none'}")
        lines.append(f"Duplicate rows       : {self.duplicate_rows}")
        lines.append(f"Dup station/ts pairs : {self.duplicate_station_timestamps}")
        lines.append(f"Timestamp failures   : {self.timestamp_parse_failures}")
        for col, n in self.missing_values.items():
            lines.append(f"  Missing {col}: {n}")
        for col, n in self.physical_violations.items():
            lines.append(f"  Physical violation {col}: {n}")
        for w in self.warnings:
            lines.append(f"  WARN: {w}")
        lines.append(f"Overall valid        : {self.is_valid}")
        return "\n".join(lines)


def validate(df: pd.DataFrame, physical_bounds: dict[str, Any] | None = None) -> ValidationReport:
    """Run structural and physical validation checks.

    Does NOT modify the dataframe. Returns a ValidationReport.
    """
    report = ValidationReport()
    bounds = physical_bounds or PHYSICAL_BOUNDS

    # Column presence
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        report.missing_columns = missing_cols
        report.is_valid = False

    # Missing values
    for col in df.columns:
        n = int(df[col].isna().sum())
        if n > 0:
            report.missing_values[col] = n

    # Duplicate rows
    report.duplicate_rows = int(df.duplicated().sum())

    # Duplicate station/timestamp combinations
    if "station_id" in df.columns and "timestamp" in df.columns:
        report.duplicate_station_timestamps = int(
            df.duplicated(subset=["station_id", "timestamp"]).sum()
        )

    # Timestamp parse failures
    if "timestamp" in df.columns:
        report.timestamp_parse_failures = int(df["timestamp"].isna().sum())

    # Physical bounds
    for col, (lo, hi) in bounds.items():
        if col in df.columns:
            n = int(((df[col] < lo) | (df[col] > hi)).sum())
            if n > 0:
                report.physical_violations[col] = n
                report.warnings.append(
                    f"{col} has {n} values outside [{lo}, {hi}]"
                )

    logger.info(report.summarise())
    return report
