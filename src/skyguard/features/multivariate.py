"""Multivariate weather consistency features.

Fits regression models on training data to predict each sensor from the others,
then computes residuals as consistency signals.
Also computes Mahalanobis distance on the sensor vector.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.preprocessing import RobustScaler

logger = logging.getLogger(__name__)

SENSOR_COLS = [
    "temperature_c",
    "relative_humidity_pct",
    "pressure_hpa",
    "wind_speed_kmh",
    "rainfall_mm",
]


class MultivariateConsistency:
    """Fits cross-sensor regression models and computes consistency residuals."""

    def __init__(self, sensor_cols: list[str] | None = None) -> None:
        self.sensor_cols = sensor_cols or SENSOR_COLS
        self._models: dict[str, Any] = {}
        self._scaler = RobustScaler()
        self._cov_inv: np.ndarray | None = None
        self._train_mean: np.ndarray | None = None

    def _src(self, col: str, df: pd.DataFrame) -> str:
        return f"{col}_clean" if f"{col}_clean" in df.columns else col

    def fit(self, train_df: pd.DataFrame) -> "MultivariateConsistency":
        cols = self.sensor_cols
        src_cols = [self._src(c, train_df) for c in cols]
        available = [c for c in src_cols if c in train_df.columns]

        X_all = train_df[available].dropna()
        if len(X_all) < 10:
            logger.warning("Too few rows for multivariate consistency fitting.")
            return self

        # Fit cross-sensor regressors
        for i, col in enumerate(cols):
            src = self._src(col, train_df)
            if src not in train_df.columns:
                continue
            other_srcs = [s for s in available if s != src]
            if not other_srcs:
                continue
            mask = train_df[other_srcs + [src]].notna().all(axis=1)
            X_tr = train_df.loc[mask, other_srcs].values
            y_tr = train_df.loc[mask, src].values
            model = ExtraTreesRegressor(
                n_estimators=50, max_depth=4, min_samples_leaf=3, random_state=42
            )
            model.fit(X_tr, y_tr)
            self._models[col] = (model, other_srcs)

        # Fit scaler and covariance for Mahalanobis distance
        X_scaled = self._scaler.fit_transform(X_all.values)
        self._train_mean = X_scaled.mean(axis=0)
        cov = np.cov(X_scaled.T)
        try:
            self._cov_inv = np.linalg.inv(cov + np.eye(cov.shape[0]) * 1e-6)
        except np.linalg.LinAlgError:
            self._cov_inv = None
            logger.warning("Covariance matrix inversion failed; Mahalanobis disabled.")

        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        cols = self.sensor_cols
        src_cols = [self._src(c, df) for c in cols]

        for col in cols:
            df[f"mv_{col}_residual"] = np.nan

        for col, (model, other_srcs) in self._models.items():
            src = self._src(col, df)
            if src not in df.columns:
                continue
            mask = df[other_srcs + [src]].notna().all(axis=1)
            if mask.sum() == 0:
                continue
            X_pred = df.loc[mask, other_srcs].values
            y_pred = model.predict(X_pred)
            df.loc[mask, f"mv_{col}_residual"] = df.loc[mask, src].values - y_pred

        # Mahalanobis distance
        df["mahalanobis_distance"] = np.nan
        if self._cov_inv is not None:
            available = [c for c in src_cols if c in df.columns]
            mask = df[available].notna().all(axis=1)
            if mask.sum() > 0:
                X = self._scaler.transform(df.loc[mask, available].values)
                diff = X - self._train_mean
                mah = np.sqrt(np.einsum("ij,jk,ik->i", diff, self._cov_inv, diff))
                df.loc[mask, "mahalanobis_distance"] = mah

        return df
