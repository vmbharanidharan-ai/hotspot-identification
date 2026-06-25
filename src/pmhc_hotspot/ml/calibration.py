"""Probability calibration and learned ensemble weights."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_auc_score


def calibrate_estimator(estimator, *, cv: int = 3):
    """Wrap a fitted or unfitted estimator with Platt (sigmoid) calibration."""
    cv = max(2, cv)
    return CalibratedClassifierCV(estimator, method="sigmoid", cv=cv)


def learn_hybrid_alpha(
    stat_probs: pd.Series | np.ndarray,
    ml_probs: pd.Series | np.ndarray,
    labels: pd.Series | np.ndarray,
    *,
    grid_size: int = 21,
) -> float:
    """
    Choose blend weight α that maximizes ROC-AUC on OOF predictions.

    hybrid = α · P_stat + (1 − α) · P_ml
    """
    stat = np.asarray(stat_probs, dtype=float)
    ml = np.asarray(ml_probs, dtype=float)
    y = np.asarray(labels, dtype=int)
    if len(np.unique(y)) < 2:
        return 0.5

    best_alpha = 0.5
    best_auc = -1.0
    for alpha in np.linspace(0.0, 1.0, grid_size):
        blend = alpha * stat + (1.0 - alpha) * ml
        try:
            auc = roc_auc_score(y, blend)
        except ValueError:
            continue
        if auc > best_auc:
            best_auc = auc
            best_alpha = float(alpha)
    return best_alpha
