"""Evaluation metrics — comprehensive reporting for imbalanced classification."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    auc,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
)


def evaluate_classifier(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: np.ndarray,
    class_names: list[str],
) -> dict[str, Any]:
    """Compute comprehensive classification metrics.

    Primary metrics: macro F1, per-class recall, PR-AUC, false alarm rate.
    Accuracy is reported but NOT used as primary selection criterion.
    """
    n_classes = len(class_names)
    labels = list(range(n_classes))
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    report = classification_report(
        y_true, y_pred,
        labels=labels,
        target_names=class_names,
        output_dict=True,
        zero_division=0,
    )

    # Per-class PR-AUC
    pr_auc: dict[str, float] = {}
    brier: dict[str, float] = {}
    for i, cls in enumerate(class_names):
        binary = (y_true == i).astype(int)
        if binary.sum() > 0 and y_proba.shape[1] > i:
            prec, rec, _ = precision_recall_curve(binary, y_proba[:, i])
            pr_auc[cls] = float(auc(rec, prec))
            brier[cls] = float(brier_score_loss(binary, y_proba[:, i]))

    # False alarm rate per class
    far: dict[str, float] = {}
    for i, cls in enumerate(class_names):
        tp = cm[i, i]
        fp = cm[:, i].sum() - tp
        fn = cm[i, :].sum() - tp
        tn = cm.sum() - tp - fp - fn
        far[cls] = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0

    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
        "per_class_report": report,
        "confusion_matrix": cm.tolist(),
        "pr_auc": pr_auc,
        "brier_score": brier,
        "false_alarm_rate": far,
    }
