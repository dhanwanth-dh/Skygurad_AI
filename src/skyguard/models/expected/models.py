"""Expected-value models for temperature, humidity, and pressure.

Trains multiple regression model candidates (Ridge, Random Forest, Extra Trees,
XGBoost, Gradient Boosting, HistGradientBoosting) using chronological validation,
evaluates MAE, RMSE, R², dynamically calculates inverse-MAE ensemble weights,
and produces expected sensor values with model agreement and disagreement metrics.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import RobustScaler

logger = logging.getLogger(__name__)

TARGETS = ["temperature_c", "relative_humidity_pct", "pressure_hpa"]

# Normalization scales for agreement/disagreement computation per target
TARGET_TYPICAL_SCALES = {
    "temperature_c": 5.0,        # 5 °C spread represents substantial disagreement
    "relative_humidity_pct": 15.0, # 15% spread represents substantial disagreement
    "pressure_hpa": 6.0,          # 6 hPa spread represents substantial disagreement
}


def _feature_cols_for_target(target: str, all_cols: list[str]) -> list[str]:
    """Select feature columns for a given target, excluding the target and generated downstream signals."""
    exclude_prefixes = (
        "qf_", "qc_", "rule_", "predicted_", "expected_", "anomaly_",
        "if_", "lof_", "ocsvm_", "elliptic_", "mahalanobis_", "robust_z_",
        f"{target}_lag", f"{target}_roll", f"{target}_delta", f"{target}_pred_",
    )
    exclude_exact = {
        target,
        f"{target}_clean",
        f"{target}_baseline",
        f"{target}_deviation",
        f"{target}_robust_z",
        f"{target}_residual",
        "ground_truth_label",
        "fault_description",
        "station_name",
        "timestamp",
        "station_id",
        "latitude",
        "longitude",
        "statistical_anomaly_score",
        "combined_anomaly_score",
    }
    numeric_cols = [
        c for c in all_cols
        if c not in exclude_exact
        and not any(c.startswith(p) for p in exclude_prefixes)
        and not c.endswith("_residual")
        and not c.endswith("_disagreement")
        and not c.endswith("_variance")
        and not c.endswith("_model_agreement")
    ]
    return numeric_cols


class ExpectedValueModel:
    """Multi-model ensemble predicting expected sensor values."""

    def __init__(self, target: str) -> None:
        self.target = target
        self._scaler = RobustScaler()
        self._imputer = SimpleImputer(strategy="median")
        self._feature_cols: list[str] = []
        self._fitted_models: dict[str, Any] = {}
        self.weights: dict[str, float] = {}
        self.val_metrics: dict[str, dict[str, float]] = {}
        self.summary_val_metrics: dict[str, float] = {}
        self._best_name: str = ""
        self._model: Any = None  # Pointer to best candidate or ensemble for backwards-compat

    def _build_candidates(self) -> dict[str, Any]:
        """Instantiate candidate regressors."""
        candidates = {
            "ridge": Ridge(alpha=10.0),
            "random_forest": RandomForestRegressor(
                n_estimators=100, max_depth=8, min_samples_leaf=3, random_state=42, n_jobs=-1
            ),
            "extra_trees": ExtraTreesRegressor(
                n_estimators=100, max_depth=8, min_samples_leaf=3, random_state=42, n_jobs=-1
            ),
            "hist_gradient_boosting": HistGradientBoostingRegressor(
                max_iter=100, max_depth=6, learning_rate=0.08, random_state=42
            ),
            "gradient_boosting": GradientBoostingRegressor(
                n_estimators=50, max_depth=3, subsample=0.5, learning_rate=0.08, random_state=42
            ),
        }

        # XGBoost candidate
        try:
            from xgboost import XGBRegressor
            candidates["xgboost"] = XGBRegressor(
                n_estimators=100, max_depth=5, learning_rate=0.08,
                subsample=0.8, random_state=42, n_jobs=-1, verbosity=0
            )
        except ImportError:
            logger.debug("XGBoost not installed; skipping regressor candidate.")

        # LightGBM candidate (optional)
        try:
            from lightgbm import LGBMRegressor
            candidates["lightgbm"] = LGBMRegressor(
                n_estimators=100, max_depth=4, learning_rate=0.05,
                random_state=42, verbose=-1
            )
        except ImportError:
            pass

        return candidates

    def fit(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame,
    ) -> "ExpectedValueModel":
        all_cols = list(train_df.columns)
        self._feature_cols = _feature_cols_for_target(self.target, all_cols)

        # Filter to numeric columns with sufficient observations
        self._feature_cols = [
            c for c in self._feature_cols
            if pd.api.types.is_numeric_dtype(train_df[c])
            and train_df[c].notna().sum() > 10
        ]

        src = f"{self.target}_clean" if f"{self.target}_clean" in train_df.columns else self.target
        mask_tr = train_df[src].notna()
        X_tr_raw = train_df.loc[mask_tr, self._feature_cols].values
        y_tr = train_df.loc[mask_tr, src].values

        mask_val = val_df[src].notna()
        X_val_raw = val_df.loc[mask_val, self._feature_cols].values
        y_val = val_df.loc[mask_val, src].values

        if len(X_tr_raw) < 5:
            logger.warning("Insufficient training data for %s expected-value models.", self.target)
            return self
        if len(X_val_raw) < 2:
            logger.warning("Insufficient val data for %s; using last 5 train rows for benchmark.", self.target)
            X_val_raw = X_tr_raw[-5:]
            y_val = y_tr[-5:]

        X_tr = self._imputer.fit_transform(X_tr_raw)
        X_val = self._imputer.transform(X_val_raw)
        X_tr_s = self._scaler.fit_transform(X_tr)
        X_val_s = self._scaler.transform(X_val)

        raw_weights: dict[str, float] = {}
        best_mae = np.inf
        candidates = self._build_candidates()

        for name, model in candidates.items():
            try:
                model.fit(X_tr_s, y_tr)
                preds = model.predict(X_val_s)
                mae = float(mean_absolute_error(y_val, preds))
                mse = float(mean_squared_error(y_val, preds))
                rmse = float(np.sqrt(mse))
                r2 = float(r2_score(y_val, preds))

                self.val_metrics[name] = {
                    "mae": round(mae, 4),
                    "rmse": round(rmse, 4),
                    "r2": round(r2, 4),
                }
                self._fitted_models[name] = model
                logger.info("  %s [%s] val MAE=%.3f RMSE=%.3f R2=%.3f", self.target, name, mae, rmse, r2)

                # Weight proportional to inverse MAE if model is valid
                if r2 > -1.0 and mae > 0:
                    raw_w = 1.0 / (mae + 1e-4)
                    raw_weights[name] = raw_w
                else:
                    raw_weights[name] = 0.0

                if mae < best_mae:
                    best_mae = mae
                    self._best_name = name
                    self._model = model

            except Exception as exc:
                logger.warning("Candidate %s for %s failed: %s", name, self.target, exc)
                self.val_metrics[name] = {"mae": 999.0, "rmse": 999.0, "r2": -99.0, "error": str(exc)}
                raw_weights[name] = 0.0

        # Normalize weights
        total_w = sum(raw_weights.values())
        if total_w > 0:
            self.weights = {k: round(v / total_w, 4) for k, v in raw_weights.items()}
        else:
            # Fallback uniform weights for fitted models
            n_models = max(1, len(self._fitted_models))
            self.weights = {k: round(1.0 / n_models, 4) for k in self._fitted_models}

        # Calculate ensemble validation performance
        ensemble_val_preds = self._predict_ensemble_array(X_val_s)
        ens_mae = float(mean_absolute_error(y_val, ensemble_val_preds))
        ens_rmse = float(np.sqrt(mean_squared_error(y_val, ensemble_val_preds)))
        ens_r2 = float(r2_score(y_val, ensemble_val_preds))

        self.summary_val_metrics = {
            "mae": round(ens_mae, 4),
            "rmse": round(ens_rmse, 4),
            "r2": round(ens_r2, 4),
            "best_single_model": self._best_name,
            "best_single_mae": round(best_mae, 4),
        }

        logger.info(
            "Ensemble for %s fitted (%d models, val MAE=%.3f, R2=%.3f, Best: %s [MAE=%.3f])",
            self.target, len(self._fitted_models), ens_mae, ens_r2, self._best_name, best_mae
        )
        return self

    def _prepare_features(self, df: pd.DataFrame) -> tuple[np.ndarray, pd.Series]:
        mask = pd.Series(True, index=df.index)
        if len(self._feature_cols) == 0:
            return np.zeros((len(df), 0)), mask

        # Handle missing columns robustly
        available_cols = [c for c in self._feature_cols if c in df.columns]
        missing_cols = [c for c in self._feature_cols if c not in df.columns]

        if missing_cols:
            X_df = df[available_cols].copy()
            for mc in missing_cols:
                X_df[mc] = np.nan
            X_raw = X_df[self._feature_cols].values
        else:
            X_raw = df[self._feature_cols].values

        X = self._imputer.transform(X_raw)
        X_s = self._scaler.transform(X)
        return X_s, mask

    def _predict_ensemble_array(self, X_s: np.ndarray) -> np.ndarray:
        if not self._fitted_models:
            return np.full(len(X_s), np.nan)

        weighted_sum = np.zeros(len(X_s))
        total_weight = 0.0

        for name, model in self._fitted_models.items():
            w = self.weights.get(name, 0.0)
            if w <= 0:
                continue
            try:
                preds = model.predict(X_s)
                weighted_sum += w * preds
                total_weight += w
            except Exception as exc:
                logger.warning("Model %s prediction failed: %s", name, exc)

        if total_weight > 0:
            return weighted_sum / total_weight
        elif self._model is not None:
            return self._model.predict(X_s)
        return np.full(len(X_s), np.nan)

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Return weighted ensemble predictions."""
        if not self._fitted_models and self._model is None:
            return np.full(len(df), np.nan)
        X_s, mask = self._prepare_features(df)
        preds = np.full(len(df), np.nan)
        if len(X_s) > 0:
            preds = self._predict_ensemble_array(X_s)
        return preds

    def predict_detailed(self, df: pd.DataFrame) -> dict[str, Any]:
        """Compute ensemble predictions, individual model predictions, variance, and agreement."""
        if not self._fitted_models and self._model is None:
            n = len(df)
            return {
                "ensemble_prediction": np.full(n, np.nan),
                "candidate_predictions": {},
                "model_variance": np.zeros(n),
                "model_agreement": np.ones(n),
                "model_disagreement": np.zeros(n),
            }

        X_s, _ = self._prepare_features(df)
        candidate_preds: dict[str, np.ndarray] = {}
        preds_matrix = []
        weights_list = []

        for name, model in self._fitted_models.items():
            try:
                p = model.predict(X_s)
                candidate_preds[name] = p
                w = self.weights.get(name, 0.0)
                if w > 0:
                    preds_matrix.append(p)
                    weights_list.append(w)
            except Exception as exc:
                logger.warning("Prediction failed for %s: %s", name, exc)

        if preds_matrix:
            arr = np.array(preds_matrix)  # shape (n_models, n_samples)
            w_arr = np.array(weights_list)[:, np.newaxis]
            w_arr = w_arr / w_arr.sum(axis=0, keepdims=True)

            ens_pred = (arr * w_arr).sum(axis=0)
            # Weighted variance across models
            var = np.sum(w_arr * ((arr - ens_pred[np.newaxis, :]) ** 2), axis=0)
            std = np.sqrt(var)

            typical_scale = TARGET_TYPICAL_SCALES.get(self.target, 5.0)
            # Agreement: 1.0 when models produce identical outputs; decreases smoothly with spread
            agreement = 1.0 / (1.0 + (std / (typical_scale * 0.5)))
            disagreement = 1.0 - agreement
        else:
            ens_pred = self.predict(df)
            var = np.zeros(len(df))
            agreement = np.ones(len(df))
            disagreement = np.zeros(len(df))

        return {
            "ensemble_prediction": ens_pred,
            "candidate_predictions": candidate_preds,
            "model_variance": var,
            "model_agreement": np.clip(agreement, 0.0, 1.0),
            "model_disagreement": np.clip(disagreement, 0.0, 1.0),
        }

    def add_residuals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add predicted_<target>, <target>_residual, agreement, and variance columns."""
        df = df.copy()
        src = f"{self.target}_clean" if f"{self.target}_clean" in df.columns else self.target
        detailed = self.predict_detailed(df)

        preds = detailed["ensemble_prediction"]
        df[f"predicted_{self.target}"] = preds
        df[f"expected_{self.target}"] = preds
        df[f"{self.target}_residual"] = df[src] - preds
        df[f"expected_{self.target}_model_agreement"] = detailed["model_agreement"]
        df[f"expected_{self.target}_variance"] = detailed["model_variance"]
        df[f"expected_{self.target}_disagreement"] = detailed["model_disagreement"]

        # Also populate candidate prediction columns for explainability
        for m_name, m_preds in detailed["candidate_predictions"].items():
            df[f"{self.target}_pred_{m_name}"] = m_preds

        return df


def fit_all_expected_models(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    targets: list[str] | None = None,
) -> dict[str, ExpectedValueModel]:
    """Fit expected-value multi-model ensembles for all targets."""
    targets = targets or TARGETS
    models = {}
    for target in targets:
        logger.info("Fitting multi-model expected-value ensemble for: %s", target)
        m = ExpectedValueModel(target)
        m.fit(train_df, val_df)
        models[target] = m
    return models


def apply_expected_models(
    df: pd.DataFrame,
    models: dict[str, ExpectedValueModel],
) -> pd.DataFrame:
    for target, model in models.items():
        df = model.add_residuals(df)
    return df
