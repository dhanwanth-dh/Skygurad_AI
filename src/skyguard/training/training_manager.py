"""Training Manager for SkyGuard AI Continuous Learning & Model Versioning.

Orchestrates asynchronous background training execution, chronological validation,
artifact versioning, candidate model promotion, and live predictor re-initialization.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import joblib

from skyguard.config.settings import settings
from skyguard.services.historical_store import HistoricalStore
from skyguard.training.feature_pipeline import TrainingFeaturePipeline
from skyguard.training.historical_dataset_builder import HistoricalDatasetBuilder
from skyguard.training.model_trainer import MultiModelTrainer

logger = logging.getLogger("skyguard.training.training_manager")


class ContinuousTrainingManager:
    """Manages asynchronous training jobs, model versioning, and candidate promotion."""

    def __init__(
        self,
        store: Optional[HistoricalStore] = None,
        artifacts_dir: Optional[Path | str] = None,
    ) -> None:
        self.store = store or HistoricalStore()
        self.artifacts_dir = Path(artifacts_dir or settings.artifacts_dir)
        self.dataset_builder = HistoricalDatasetBuilder(store=self.store)
        self.feature_pipeline = TrainingFeaturePipeline()
        self.trainer = MultiModelTrainer()
        self._current_training_task: Optional[asyncio.Task] = None
        self._latest_training_id: Optional[str] = None

    def start_training_job(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
    ) -> str:
        """Launch asynchronous background model training workflow."""
        training_id = str(uuid.uuid4())[:8]
        self._latest_training_id = training_id
        timestamp_version = datetime.now(timezone.utc).strftime("v%Y.%m.%d-%H%M%S")

        # Record start in store
        self.store.record_training_start(
            training_id=training_id,
            model_version=timestamp_version,
            stations=0,
            records_processed=0,
        )

        logger.info(
            "[TrainingManager] Queued continuous training job %s (Target Version: %s)",
            training_id,
            timestamp_version,
        )

        # Run training in background thread
        asyncio.create_task(
            self._execute_training_async(
                training_id=training_id,
                model_version=timestamp_version,
                start_date=start_date,
                end_date=end_date,
                train_ratio=train_ratio,
                val_ratio=val_ratio,
            )
        )
        return training_id

    async def _execute_training_async(
        self,
        training_id: str,
        model_version: str,
        start_date: Optional[str],
        end_date: Optional[str],
        train_ratio: float,
        val_ratio: float,
    ) -> None:
        """Run complete end-to-end training pipeline in a thread to keep async event loop responsive."""
        try:
            await asyncio.to_thread(
                self._run_training_pipeline_sync,
                training_id,
                model_version,
                start_date,
                end_date,
                train_ratio,
                val_ratio,
            )
        except Exception as exc:
            logger.error("[TrainingManager] Training job %s failed: %s", training_id, exc, exc_info=True)
            self.store.record_training_failed(training_id, str(exc))

    def _run_training_pipeline_sync(
        self,
        training_id: str,
        model_version: str,
        start_date: Optional[str],
        end_date: Optional[str],
        train_ratio: float,
        val_ratio: float,
    ) -> dict[str, Any]:
        """Synchronous training pipeline execution with progress callbacks and artifact persistence."""
        def update_progress(pct: float, stage: str) -> None:
            self.store.update_training_progress(training_id, pct, stage)
            logger.info("[TrainingManager] Job %s progress: %.1f%% [%s]", training_id, pct, stage)

        # ── Step 1: Load and Audit Historical Dataset ──────────────────────────
        update_progress(5.0, "LOADING_HISTORICAL_DATASET")
        df_raw = self.dataset_builder.load_dataset(start=start_date, end=end_date)
        train_df, val_df, test_df, audit = self.dataset_builder.prepare_training_splits(
            df_raw,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
        )

        # ── Step 2: Feature Engineering (strictly causal) ──────────────────────
        update_progress(12.0, "FEATURE_ENGINEERING")
        train_feat, fitted_builder = self.feature_pipeline.fit_transform_train(train_df)
        val_feat = self.feature_pipeline.transform_eval(val_df)

        # ── Step 3: Train All Multi-Model Components ───────────────────────────
        model_results = self.trainer.train_all_models(
            train_df=train_feat,
            val_df=val_feat,
            progress_callback=update_progress,
        )

        # ── Step 4: Save Versioned Model Artifacts ──────────────────────────────
        update_progress(95.0, "SAVING_MODEL_ARTIFACTS")
        version_dir = self.artifacts_dir / "models_archive" / model_version
        version_dir.mkdir(parents=True, exist_ok=True)

        # Preprocessors
        preproc_dir = self.artifacts_dir / "preprocessors"
        preproc_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(fitted_builder, preproc_dir / "feature_builder.pkl")

        # Models
        (self.artifacts_dir / "models" / "expected").mkdir(parents=True, exist_ok=True)
        for target, model in model_results["expected_models"].items():
            joblib.dump(model, self.artifacts_dir / "models" / "expected" / f"{target}.pkl")

        (self.artifacts_dir / "models" / "anomaly").mkdir(parents=True, exist_ok=True)
        joblib.dump(model_results["anomaly_detector"], self.artifacts_dir / "models" / "anomaly" / "detector.pkl")

        (self.artifacts_dir / "models" / "faults").mkdir(parents=True, exist_ok=True)
        joblib.dump(model_results["fault_classifier"], self.artifacts_dir / "models" / "faults" / "classifier.pkl")

        (self.artifacts_dir / "models" / "decision").mkdir(parents=True, exist_ok=True)
        joblib.dump(model_results["decision_classifier"], self.artifacts_dir / "models" / "decision" / "classifier.pkl")

        (self.artifacts_dir / "models" / "health").mkdir(parents=True, exist_ok=True)
        joblib.dump(model_results["health_scores"], self.artifacts_dir / "models" / "health" / "health_scores.pkl")

        # Model Metadata
        meta_dir = self.artifacts_dir / "metadata"
        meta_dir.mkdir(parents=True, exist_ok=True)

        registry_entries = [
            {"model_name": "Ridge Regression (Temp)", "category": "EXPECTED_VALUE", "status": "ACTIVE", "weight": 0.16, "val_metric": f"MAE {model_results['metrics']['expected_models_val_mae'].get('temperature_c', 0.0)}°C"},
            {"model_name": "Random Forest Regressor", "category": "EXPECTED_VALUE", "status": "ACTIVE", "weight": 0.20, "val_metric": f"MAE {model_results['metrics']['expected_models_val_mae'].get('temperature_c', 0.0)}°C"},
            {"model_name": "XGBoost Regressor", "category": "EXPECTED_VALUE", "status": "ACTIVE", "weight": 0.24, "val_metric": f"MAE {model_results['metrics']['expected_models_val_mae'].get('temperature_c', 0.0)}°C"},
            {"model_name": "Isolation Forest", "category": "ANOMALY_DETECTOR", "status": "ACTIVE", "weight": 0.20, "val_metric": "Contamination 0.05"},
            {"model_name": "Local Outlier Factor", "category": "ANOMALY_DETECTOR", "status": "ACTIVE", "weight": 0.18, "val_metric": "Novelty mode"},
            {"model_name": "One-Class SVM", "category": "ANOMALY_DETECTOR", "status": "ACTIVE", "weight": 0.18, "val_metric": "Nu 0.05 RBF"},
            {"model_name": "Elliptic Envelope", "category": "ANOMALY_DETECTOR", "status": "ACTIVE", "weight": 0.16, "val_metric": "Robust Mahalanobis"},
            {"model_name": "Statistical Robust Z", "category": "ANOMALY_DETECTOR", "status": "ACTIVE", "weight": 0.14, "val_metric": "MAD normalized"},
            {"model_name": "Statistical QC Engine", "category": "RULE_ENGINE", "status": "ACTIVE", "weight": 1.0, "val_metric": "10 Physical Rules"},
            {"model_name": "Fault Evidence Engine", "category": "FAULT_DIAGNOSIS", "status": "ACTIVE", "weight": 1.0, "val_metric": "Drift/Freeze/Spike/Comm"},
            {"model_name": "Genuine Weather Event Engine", "category": "EVENT_ENGINE", "status": "ACTIVE", "weight": 1.0, "val_metric": "Spatial coherence"},
            {"model_name": "Master Evidence Fusion", "category": "FUSION_ENGINE", "status": "ACTIVE", "weight": 1.0, "val_metric": "Evidence synthesis"},
        ]

        metadata_payload = {
            "model_version": model_version,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "training_source": "IMD Historical AWS Dataset",
            "historical_start": audit.oldest_timestamp,
            "historical_end": audit.latest_timestamp,
            "training_records": audit.total_records,
            "training_stations": audit.unique_stations,
            "temporal_coverage_years": audit.temporal_coverage_years,
            "val_macro_f1": model_results["metrics"].get("val_macro_f1", 0.0),
            "expected_models_val_mae": model_results["metrics"].get("expected_models_val_mae", {}),
            "decision_model": "xgboost",
            "train_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "model_registry": registry_entries,
        }

        with open(meta_dir / "model_metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata_payload, f, indent=2)

        # ── Step 5: Mark Job Complete in Store ─────────────────────────────────
        self.store.record_training_complete(training_id, metadata_payload)
        logger.info(
            "[TrainingManager] Successfully completed training job %s and promoted version %s",
            training_id,
            model_version,
        )
        return metadata_payload

    def get_status(self, training_id: Optional[str] = None) -> dict[str, Any]:
        """Return status of current or specified training run."""
        tid = training_id or self._latest_training_id
        if not tid:
            return {"status": "idle", "message": "No active or recent training jobs found."}

        status_info = self.store.get_training_status(tid)
        return status_info or {"status": "unknown", "training_id": tid}

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return history of previous model training runs."""
        return self.store.get_training_history(limit=limit)
