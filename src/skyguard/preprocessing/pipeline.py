"""Preprocessing pipeline — orchestrates quality flags, imputation, and clipping."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from skyguard.preprocessing.cleaner import clip_physical, impute_per_station
from skyguard.preprocessing.quality import PHYSICAL_BOUNDS, add_quality_flags

logger = logging.getLogger(__name__)


def run_preprocessing(df: pd.DataFrame) -> pd.DataFrame:
    """Full preprocessing pipeline.

    1. Add quality flags.
    2. Impute missing values per station (forward/backward fill).
    3. Clip _clean columns to physical bounds.

    Returns a new dataframe; raw columns are never modified.
    """
    logger.info("Running preprocessing pipeline on %d rows.", len(df))
    df = add_quality_flags(df, PHYSICAL_BOUNDS)
    df = impute_per_station(df)
    df = clip_physical(df, PHYSICAL_BOUNDS)
    logger.info("Preprocessing complete. Columns: %d", df.shape[1])
    return df


def save_processed(df: pd.DataFrame, output_dir: Path, filename: str = "processed.parquet") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / filename
    df.to_parquet(out_path, index=False)
    logger.info("Saved processed data to %s", out_path)
    return out_path
