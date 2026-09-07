"""Anomaly detection — Multi-model ensemble with score normalization and consensus.

Implements 6 complementary anomaly detectors:
1. Isolation Forest (global isolation trees)
2. Local Outlier Factor (local density estimation)
3. One-Class SVM (boundary support vectors)
4. Elliptic Envelope (robust covariance ellipsoid)
5. Mahalanobis Distance (multivariate distribution outlier)
6. Robust Z-Score (MAD-based deviation across sensors)
+ Optional Autoencoder (disabled by default on small datasets)

Learns normalization thresholds strictly on training data and computes
both a weighted combined anomaly score and a model consensus agreement.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.covariance import EllipticEnvelope
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import RobustScaler
from sklearn.svm import OneClassSVM

from skyguard.models.anomaly.autoencoder import AutoencoderDetector

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    "isolation_forest": 0.25,
    "lof": 0.20,
    "one_class_svm": 0.20,
    "elliptic_envelope": 0.15,
    "mahalanobis": 0.10,
    "robust_zscore": 0.10,
}


def _anomaly_feature_cols(df: pd.DataFrame) -> list[str]:
    """Select numeric, non-target, non-flag columns for anomaly detection."""
    exclude_prefixes = (
        "qf_", "qc_", "rule_", "ground_truth", "fault_desc", "station_name", "timestamp",
        "predicted_", "expected_", "anomaly_", "if_", "lof_", "ocsvm_", "elliptic_",
        "mahalanobis_", "robust_z_",
    )
    exclude_exact = {"station_id", "latitude", "longitude", "statistical_anomaly_score", "combined_anomaly_score"}
    cols = [
        c for c in df.columns
        if pd.api.types.is_numeric_dtype(df[c])
        and c not in exclude_exact
        and not any(c.startswith(p) for p in exclude_prefixes)
        and not c.endswith("_residual")
        and not c.endswith("_disagreement")
        and not c.endswith("_variance")
        and not c.endswith("_model_agreement")
    ]
    return cols


class AnomalyDetector:
    """Multi-detector unsupervised anomaly ensemble with normalization and consensus."""

    def __init__(
        self,
        if_contamination: float = 0.05,
        lof_n_neighbors: int = 5,
        lof_contamination: float = 0.05,
        ocsvm_nu: float = 0.05,
        elliptic_contamination: float = 0.05,
        weights: dict[str, float] | None = None,
        random_state: int = 42,
    ) -> None:
        self.random_state = random_state
        self.weights = weights or DEFAULT_WEIGHTS.copy()

        # Instantiate detectors
        self._if = IsolationForest(
            n_estimators=100,
            contamination=if_contamination,
            random_state=random_state,
            n_jobs=-1,
        )
        self._lof = LocalOutlierFactor(
            n_neighbors=lof_n_neighbors,
            contamination=lof_contamination,
            novelty=True,
            n_jobs=-1,
        )
        self._ocsvm = OneClassSVM(
            nu=ocsvm_nu,
            kernel="rbf",
            gamma="scale",
        )
        self._elliptic = EllipticEnvelope(
            contamination=elliptic_contamination,
            support_fraction=0.8,
            random_state=random_state,
        )
        self._autoencoder = AutoencoderDetector(enabled=False)

        self._scaler = RobustScaler()
        self._imputer = SimpleImputer(strategy="median")
        self._feature_cols: list[str] = []

        # Training threshold and normalization stats
        self._norm_params: dict[str, dict[str, float]] = {}
        self._thresholds: dict[str, float] = {}
        self._cov_inv: np.ndarray | None = None
        self._train_mean: np.ndarray | None = None
        self.detector_statuses: dict[str, bool] = {
            "isolation_forest": True,
            "lof": True,
            "one_class_svm": True,
            "elliptic_envelope": True,
            "mahalanobis": True,
            "robust_zscore": True,
            "autoencoder": False,
        }

    def _normalize(self, raw_scores: np.ndarray, name: str) -> np.ndarray:
        """Normalize raw scores into [0, 1] using training distribution parameters."""
        params = self._norm_params.get(name, {"p5": 0.0, "p95": 1.0})
        p5 = params.get("p5", 0.0)
        p95 = params.get("p95", 1.0)
        denom = max(p95 - p5, 1e-6)

        # Scale so p5 -> 0.05, p95 -> 0.85, higher scores smoothly approach 1.0
        scaled = (raw_scores - p5) / denom
        norm = np.clip(scaled * 0.80 + 0.05, 0.0, 1.0)
        return norm

    def fit(self, train_df: pd.DataFrame) -> "AnomalyDetector":
        self._feature_cols = _anomaly_feature_cols(train_df)
        self._feature_cols = [
            c for c in self._feature_cols if train_df[c].notna().sum() > 10
        ]

        X_raw = train_df[self._feature_cols].values
        X = self._imputer.fit_transform(X_raw)
        X_s = self._scaler.fit_transform(X)

        n_samples = len(X_s)
        # Subsample for O(N^2) models if dataset is large
        if n_samples > 4000:
            rng = np.random.RandomState(self.random_state)
            sub_idx = rng.choice(n_samples, 4000, replace=False)
            X_s_sub = X_s[sub_idx]
        else:
            X_s_sub = X_s

        # 1. Isolation Forest
        try:
            self._if.fit(X_s)
            if_raw = -self._if.score_samples(X_s_sub)
            self._norm_params["if"] = {
                "p5": float(np.percentile(if_raw, 5)),
                "p95": float(np.percentile(if_raw, 95)),
            }
            self._thresholds["if"] = float(np.percentile(if_raw, 95))
            self.detector_statuses["isolation_forest"] = True
        except Exception as exc:
            logger.warning("Isolation Forest fitting failed: %s", exc)
            self.detector_statuses["isolation_forest"] = False

        # 2. Local Outlier Factor
        try:
            self._lof.fit(X_s_sub)
            lof_raw = -self._lof.score_samples(X_s_sub)
            self._norm_params["lof"] = {
                "p5": float(np.percentile(lof_raw, 5)),
                "p95": float(np.percentile(lof_raw, 95)),
            }
            self._thresholds["lof"] = float(np.percentile(lof_raw, 95))
            self.detector_statuses["lof"] = True
        except Exception as exc:
            logger.warning("LOF fitting failed: %s", exc)
            self.detector_statuses["lof"] = False

        # 3. One-Class SVM
        try:
            self._ocsvm.fit(X_s_sub)
            ocsvm_raw = -self._ocsvm.score_samples(X_s_sub)
            self._norm_params["ocsvm"] = {
                "p5": float(np.percentile(ocsvm_raw, 5)),
                "p95": float(np.percentile(ocsvm_raw, 95)),
            }
            self._thresholds["ocsvm"] = float(np.percentile(ocsvm_raw, 95))
            self.detector_statuses["one_class_svm"] = True
        except Exception as exc:
            logger.warning("One-Class SVM fitting failed: %s", exc)
            self.detector_statuses["one_class_svm"] = False

        # 4. Elliptic Envelope
        try:
            self._elliptic.fit(X_s_sub)
            elliptic_raw = -self._elliptic.score_samples(X_s_sub)
            self._norm_params["elliptic"] = {
                "p5": float(np.percentile(elliptic_raw, 5)),
                "p95": float(np.percentile(elliptic_raw, 95)),
            }
            self._thresholds["elliptic"] = float(np.percentile(elliptic_raw, 95))
            self.detector_statuses["elliptic_envelope"] = True
        except Exception as exc:
            logger.warning("Elliptic Envelope fitting failed: %s", exc)
            self.detector_statuses["elliptic_envelope"] = False

        # 5. Mahalanobis Distance
        try:
            self._train_mean = X_s.mean(axis=0)
            cov = np.cov(X_s.T)
            self._cov_inv = np.linalg.pinv(cov + np.eye(cov.shape[0]) * 1e-5)
            diff = X_s - self._train_mean
            mah_raw = np.sqrt(np.einsum("ij,jk,ik->i", diff, self._cov_inv, diff))
            self._norm_params["mahalanobis"] = {
                "p5": float(np.percentile(mah_raw, 5)),
                "p95": float(np.percentile(mah_raw, 95)),
            }
            self._thresholds["mahalanobis"] = float(np.percentile(mah_raw, 95))
            self.detector_statuses["mahalanobis"] = True
        except Exception as exc:
            logger.warning("Mahalanobis detector fitting failed: %s", exc)
            self.detector_statuses["mahalanobis"] = False

        # 6. Robust Z-score across sensor deviation columns
        try:
            z_cols = [c for c in train_df.columns if c.endswith("_robust_z")]
            if z_cols:
                z_vals = train_df[z_cols].abs().max(axis=1).fillna(0.0).values
            else:
                z_vals = np.abs(X_s).max(axis=1)
            self._norm_params["robust_z"] = {
                "p5": float(np.percentile(z_vals, 5)) if len(z_vals) > 0 else 0.0,
                "p95": float(np.percentile(z_vals, 95)) if len(z_vals) > 0 else 3.0,
            }
            self._thresholds["robust_z"] = 3.0
            self.detector_statuses["robust_zscore"] = True
        except Exception as exc:
            logger.warning("Robust Z-score detector fitting failed: %s", exc)
            self.detector_statuses["robust_zscore"] = False

        # 7. Optional Autoencoder
        self._autoencoder.fit(X_s)
        self.detector_statuses["autoencoder"] = self._autoencoder.is_active

        active_count = sum(1 for v in self.detector_statuses.values() if v)
        logger.info(
            "AnomalyDetector fitted on %d samples. %d active detectors: %s",
            n_samples, active_count,
            [k for k, v in self.detector_statuses.items() if v]
        )
        return self

    def score_detailed(self, df: pd.DataFrame) -> dict[str, Any]:
        """Compute normalized anomaly scores from all detectors and consensus."""
        n_samples = len(df)

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

        scores_dict: dict[str, np.ndarray] = {}
        flags_dict: dict[str, np.ndarray] = {}

        # 1. Isolation Forest
        if self.detector_statuses.get("isolation_forest", False):
            try:
                raw = -self._if.score_samples(X_s)
                norm = self._normalize(raw, "if")
                scores_dict["isolation_forest"] = norm
                flags_dict["isolation_forest"] = norm >= 0.50
            except Exception:
                scores_dict["isolation_forest"] = np.full(n_samples, 0.0)
                flags_dict["isolation_forest"] = np.zeros(n_samples, dtype=bool)

        # 2. LOF
        if self.detector_statuses.get("lof", False):
            try:
                raw = -self._lof.score_samples(X_s)
                norm = self._normalize(raw, "lof")
                scores_dict["lof"] = norm
                flags_dict["lof"] = norm >= 0.50
            except Exception:
                scores_dict["lof"] = np.full(n_samples, 0.0)
                flags_dict["lof"] = np.zeros(n_samples, dtype=bool)

        # 3. One-Class SVM
        if self.detector_statuses.get("one_class_svm", False):
            try:
                raw = -self._ocsvm.score_samples(X_s)
                norm = self._normalize(raw, "ocsvm")
                scores_dict["one_class_svm"] = norm
                flags_dict["one_class_svm"] = norm >= 0.50
            except Exception:
                scores_dict["one_class_svm"] = np.full(n_samples, 0.0)
                flags_dict["one_class_svm"] = np.zeros(n_samples, dtype=bool)

        # 4. Elliptic Envelope
        if self.detector_statuses.get("elliptic_envelope", False):
            try:
                raw = -self._elliptic.score_samples(X_s)
                norm = self._normalize(raw, "elliptic")
                scores_dict["elliptic_envelope"] = norm
                flags_dict["elliptic_envelope"] = norm >= 0.50
            except Exception:
                scores_dict["elliptic_envelope"] = np.full(n_samples, 0.0)
                flags_dict["elliptic_envelope"] = np.zeros(n_samples, dtype=bool)

        # 5. Mahalanobis
        if self.detector_statuses.get("mahalanobis", False) and self._cov_inv is not None:
            try:
                diff = X_s - self._train_mean
                raw = np.sqrt(np.einsum("ij,jk,ik->i", diff, self._cov_inv, diff))
                norm = self._normalize(raw, "mahalanobis")
                scores_dict["mahalanobis"] = norm
                flags_dict["mahalanobis"] = norm >= 0.50
            except Exception:
                scores_dict["mahalanobis"] = np.full(n_samples, 0.0)
                flags_dict["mahalanobis"] = np.zeros(n_samples, dtype=bool)

        # 6. Robust Z-score
        if self.detector_statuses.get("robust_zscore", False):
            try:
                z_cols = [c for c in df.columns if c.endswith("_robust_z")]
                if z_cols:
                    raw = df[z_cols].abs().max(axis=1).fillna(0.0).values
                else:
                    raw = np.abs(X_s).max(axis=1)
                norm = self._normalize(raw, "robust_z")
                scores_dict["robust_zscore"] = norm
                flags_dict["robust_zscore"] = norm >= 0.50
            except Exception:
                scores_dict["robust_zscore"] = np.full(n_samples, 0.0)
                flags_dict["robust_zscore"] = np.zeros(n_samples, dtype=bool)

        # Autoencoder if active
        if self.detector_statuses.get("autoencoder", False):
            try:
                _, norm = self._autoencoder.score(X_s)
                scores_dict["autoencoder"] = norm
                flags_dict["autoencoder"] = norm >= 0.50
            except Exception:
                pass

        # Calculate weighted combined score
        active_detectors = list(scores_dict.keys())
        n_detectors = max(1, len(active_detectors))

        active_weights = {k: self.weights.get(k, 1.0 / n_detectors) for k in active_detectors}
        tot_w = sum(active_weights.values()) or 1.0
        normalized_weights = {k: v / tot_w for k, v in active_weights.items()}

        combined_score = np.zeros(n_samples)
        for k, s in scores_dict.items():
            combined_score += normalized_weights[k] * s

        # Calculate consensus: count of models agreeing that observation is anomalous
        flags_matrix = np.array([flags_dict[k] for k in active_detectors]) if flags_dict else np.zeros((1, n_samples), dtype=bool)
        models_agreeing = np.sum(flags_matrix, axis=0) if flags_matrix.ndim == 2 else np.zeros(n_samples, dtype=int)
        consensus_score = models_agreeing / n_detectors
        agreement_ratio = np.clip(consensus_score, 0.0, 1.0)

        return {
            "individual_scores": scores_dict,
            "individual_flags": flags_dict,
            "combined_anomaly_score": np.clip(combined_score, 0.0, 1.0),
            "models_agreeing": models_agreeing,
            "total_models": n_detectors,
            "consensus_score": consensus_score,
            "agreement_ratio": agreement_ratio,
            "active_detectors": active_detectors,
        }

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add individual and combined anomaly scores and consensus columns."""
        df = df.copy()
        detailed = self.score_detailed(df)

        scores = detailed["individual_scores"]
        df["if_anomaly_score"] = scores.get("isolation_forest", np.nan)
        df["if_score"] = scores.get("isolation_forest", np.nan)

        df["lof_anomaly_score"] = scores.get("lof", np.nan)
        df["lof_score"] = scores.get("lof", np.nan)

        df["ocsvm_anomaly_score"] = scores.get("one_class_svm", np.nan)
        df["ocsvm_score"] = scores.get("one_class_svm", np.nan)

        df["elliptic_anomaly_score"] = scores.get("elliptic_envelope", np.nan)
        df["elliptic_score"] = scores.get("elliptic_envelope", np.nan)

        df["mahalanobis_anomaly_score"] = scores.get("mahalanobis", np.nan)
        df["mahalanobis_score"] = scores.get("mahalanobis", np.nan)

        df["robust_z_anomaly_score"] = scores.get("robust_zscore", np.nan)
        df["robust_z_score"] = scores.get("robust_zscore", np.nan)

        df["combined_anomaly_score"] = detailed["combined_anomaly_score"]
        df["anomaly_model_count"] = detailed["total_models"]
        df["anomaly_models_agreeing"] = detailed["models_agreeing"]
        df["anomaly_consensus_score"] = detailed["consensus_score"]
        df["anomaly_model_agreement"] = [
            f"{ag}/{tot} models" for ag, tot in zip(detailed["models_agreeing"], [detailed["total_models"]] * len(df))
        ]

        return df

    def get_detector_summary(self) -> dict[str, Any]:
        """Return summary of all active anomaly detectors."""
        return {
            name: {
                "active": self.detector_statuses.get(name, False),
                "weight": self.weights.get(name, 0.0),
                "threshold": self._thresholds.get(name, 0.5),
            }
            for name in self.detector_statuses
        }
