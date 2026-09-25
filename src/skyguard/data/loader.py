"""Data loader — reads and performs minimal type coercion on the raw CSV."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def load_raw(path: Path | str) -> pd.DataFrame:
    """Load the raw CSV, parse timestamps, and sort by station + time.

    Parameters
    ----------
    path:
        Absolute or relative path to the raw CSV file.

    Returns
    -------
    pd.DataFrame
        Sorted dataframe with parsed timestamps. Raw values are never modified.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Raw data not found: {path}")

    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="mixed", dayfirst=True)

    if df["timestamp"].isna().any():
        logger.warning("Some timestamps could not be parsed — check raw file.")

    df = df.drop_duplicates(subset=["station_id", "timestamp"], keep="last")
    df = df.sort_values(["station_id", "timestamp"]).reset_index(drop=True)
    logger.info("Loaded %d rows × %d columns from %s", len(df), df.shape[1], path.name)
    return df
