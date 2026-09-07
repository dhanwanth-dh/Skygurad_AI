"""Chronological train / validation / test splitter.

Splits are performed on the global timeline (across all stations simultaneously)
to avoid station leakage and future information leakage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class DataSplit:
    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame

    def report(self) -> str:
        def _label_dist(df: pd.DataFrame) -> str:
            if "ground_truth_label" not in df.columns:
                return "n/a"
            return str(df["ground_truth_label"].value_counts().to_dict())

        lines = [
            f"Train : {len(self.train):>4} rows | {self.train['timestamp'].min()} → {self.train['timestamp'].max()} | {_label_dist(self.train)}",
            f"Val   : {len(self.val):>4} rows | {self.val['timestamp'].min()} → {self.val['timestamp'].max()} | {_label_dist(self.val)}",
            f"Test  : {len(self.test):>4} rows | {self.test['timestamp'].min()} → {self.test['timestamp'].max()} | {_label_dist(self.test)}",
        ]
        return "\n".join(lines)


def chronological_split(
    df: pd.DataFrame,
    train_frac: float = 0.60,
    val_frac: float = 0.20,
    timestamp_col: str = "timestamp",
) -> DataSplit:
    """Split by unique timestamps in chronological order.

    All stations at a given timestamp land in the same split to prevent
    future information from leaking across stations.

    Parameters
    ----------
    df:
        Full dataset sorted by timestamp.
    train_frac:
        Fraction of unique timestamps for training.
    val_frac:
        Fraction of unique timestamps for validation.
        Remainder goes to test.
    timestamp_col:
        Name of the timestamp column.
    """
    unique_ts = sorted(df[timestamp_col].unique())
    n = len(unique_ts)
    n_train = int(n * train_frac)
    n_val = int(n * val_frac)

    train_ts = set(unique_ts[:n_train])
    val_ts = set(unique_ts[n_train: n_train + n_val])
    test_ts = set(unique_ts[n_train + n_val:])

    train = df[df[timestamp_col].isin(train_ts)].copy()
    val = df[df[timestamp_col].isin(val_ts)].copy()
    test = df[df[timestamp_col].isin(test_ts)].copy()

    split = DataSplit(train=train, val=val, test=test)
    logger.info("Chronological split:\n%s", split.report())
    return split
