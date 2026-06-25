"""Prediction helpers for ML pipelines."""

from __future__ import annotations

import pandas as pd


def predict_proba(model, df: pd.DataFrame) -> pd.Series:
    return pd.Series(model.predict_proba(df)[:, 1], index=df.index)


def predict_labels(model, df: pd.DataFrame, threshold: float = 0.5) -> pd.Series:
    return (predict_proba(model, df) >= threshold).astype(int)
