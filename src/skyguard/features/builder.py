"""Feature builder — orchestrates all feature engineering steps."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from skyguard.features.baseline import apply_station_baselines, compute_station_baselines
from skyguard.features.multivariate import MultivariateConsistency
from skyguard.features.spatial import add_spatial_features
from skyguard.features.temporal import add_temporal_features

logger = logging.getLogger(__name__)


class FeatureBuilder:
    """Fits feature transformers on training data and applies them to any split."""

    def __init__(
        self,
        lag_steps: list[int] | None = None,
        rolling_windows: list[int] | None = None,
        k_neighbors: int = 2,
        sensor_cols: list[str] | None = None,
    ) -> None:
        self.lag_steps = lag_steps or [1, 2, 3]
        self.rolling_windows = rolling_windows or [3, 6]
        self.k_neighbors = k_neighbors
        self.sensor_cols = sensor_cols
        self._baselines: dict[str, Any] | None = None
        self._mv_consistency: MultivariateConsistency | None = None
        self._fitted = False

    def fit(self, train_df: pd.DataFrame) -> "FeatureBuilder":
        logger.info("Fitting feature transformers on training data.")
        self._baselines = compute_station_baselines(train_df, self.sensor_cols)
        self._mv_consistency = MultivariateConsistency(self.sensor_cols)
        self._mv_consistency.fit(train_df)
        self._fitted = True
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self._fitted:
            raise RuntimeError("FeatureBuilder must be fitted before transform.")

        df = add_temporal_features(df, self.lag_steps, self.rolling_windows, self.sensor_cols)
        df = apply_station_baselines(df, self._baselines, self.sensor_cols)
        df = add_spatial_features(df, self.sensor_cols, self.k_neighbors)
        df = self._mv_consistency.transform(df)
        return df

    def fit_transform(self, train_df: pd.DataFrame) -> pd.DataFrame:
        return self.fit(train_df).transform(train_df)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        logger.info("FeatureBuilder saved to %s", path)

    @classmethod
    def load(cls, path: Path) -> "FeatureBuilder":
        obj = joblib.load(path)
        logger.info("FeatureBuilder loaded from %s", path)
        return obj
