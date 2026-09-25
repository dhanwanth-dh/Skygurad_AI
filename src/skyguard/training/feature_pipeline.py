"""Causal Feature Pipeline for SkyGuard AI Continuous Model Training.

Guarantees strict causal temporal lag construction, rolling statistics, station baselines,
and spatial covariance features fitted exclusively on training data to prevent future leakage.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import pandas as pd

from skyguard.config.settings import settings
from skyguard.features.builder import FeatureBuilder

logger = logging.getLogger("skyguard.training.feature_pipeline")


class TrainingFeaturePipeline:
    """Orchestrates causal feature extraction and baseline fitting for training splits."""

    def __init__(self, feature_builder: Optional[FeatureBuilder] = None) -> None:
        feat_cfg = settings.features
        self.builder = feature_builder or FeatureBuilder(
            lag_steps=feat_cfg.get("lags", [1, 2, 3]),
            rolling_windows=feat_cfg.get("rolling_windows", [3, 6, 12, 24]),
            sensor_cols=settings.sensor_columns,
        )

    def fit_transform_train(self, train_df: pd.DataFrame) -> tuple[pd.DataFrame, FeatureBuilder]:
        """Fit feature builder and baselines strictly on training observations only."""
        logger.info("[FeaturePipeline] Fitting feature baselines on %d training rows...", len(train_df))
        train_features = self.builder.fit_transform(train_df)
        logger.info("[FeaturePipeline] Train features generated: %d columns", train_features.shape[1])
        return train_features, self.builder

    def transform_eval(self, eval_df: pd.DataFrame) -> pd.DataFrame:
        """Apply fitted feature builder to validation or test split without refitting baselines."""
        logger.info("[FeaturePipeline] Transforming %d evaluation rows...", len(eval_df))
        eval_features = self.builder.transform(eval_df)
        return eval_features
