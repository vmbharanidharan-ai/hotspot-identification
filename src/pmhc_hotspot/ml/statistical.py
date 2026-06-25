"""Layer-2 statistical scorer: elastic-net logistic regression on structural features."""

from __future__ import annotations

import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold

from pmhc_hotspot.ml.calibration import calibrate_estimator
from pmhc_hotspot.ml.model import build_statistical_pipeline
from pmhc_hotspot.ml.train import CATEGORICAL_COLUMNS, FEATURE_COLUMNS


def base_structural_feature_columns(df: pd.DataFrame) -> list[str]:
    """Features for the statistical layer (no stat_prob / pretrain_prob)."""
    return [c for c in FEATURE_COLUMNS + CATEGORICAL_COLUMNS if c in df.columns]


def attach_stat_probabilities(structural_df: pd.DataFrame, statistical_model) -> pd.DataFrame:
    """Add calibrated statistical-layer contact probability per residue row."""
    feature_cols = base_structural_feature_columns(structural_df)
    out = structural_df.copy()
    probs = statistical_model.predict_proba(structural_df[feature_cols])[:, 1]
    out["stat_prob"] = probs
    return out


def _grouped_splits(df: pd.DataFrame, y: pd.Series, n_splits: int, random_state: int):
    groups = df["pdb_id"].astype(str)
    if y.nunique() > 1 and groups.nunique() >= n_splits:
        splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
        return splitter.split(df, y, groups)
    splitter = GroupKFold(n_splits=min(n_splits, groups.nunique()))
    return splitter.split(df, y, groups)


def train_statistical_cv(
    df: pd.DataFrame,
    *,
    label_col: str = "label",
    n_splits: int = 5,
    random_state: int = 42,
    calibrate: bool = True,
) -> dict:
    """Grouped CV for the elastic-net statistical layer."""
    feature_cols = base_structural_feature_columns(df)
    X = df[feature_cols]
    y = df[label_col].astype(int)
    if "pdb_id" not in df.columns:
        raise ValueError("Statistical training requires pdb_id for grouped CV")

    oof = pd.Series(index=df.index, dtype=float)
    fold_metrics = []
    for fold, (tr, te) in enumerate(
        _grouped_splits(df, y, n_splits, random_state), start=1
    ):
        pipe = build_statistical_pipeline(
            feature_columns=feature_cols,
            categorical_columns=[c for c in CATEGORICAL_COLUMNS if c in feature_cols],
            random_state=random_state,
        )
        if calibrate:
            cv = min(3, max(2, df.iloc[tr]["pdb_id"].nunique()))
            pipe = calibrate_estimator(pipe, cv=cv)
        pipe.fit(X.iloc[tr], y.iloc[tr])
        prob = pipe.predict_proba(X.iloc[te])[:, 1]
        oof.iloc[te] = prob
        y_te = y.iloc[te]
        fold_metrics.append(
            {
                "fold": fold,
                "roc_auc": roc_auc_score(y_te, prob) if y_te.nunique() > 1 else float("nan"),
                "avg_precision": average_precision_score(y_te, prob)
                if y_te.nunique() > 1
                else float("nan"),
            }
        )

    return {
        "stage": "statistical_elasticnet",
        "fold_metrics": fold_metrics,
        "overall": {
            "roc_auc": roc_auc_score(y, oof) if y.nunique() > 1 else float("nan"),
            "avg_precision": average_precision_score(y, oof) if y.nunique() > 1 else float("nan"),
        },
        "oof_predictions": oof,
        "n_rows": len(df),
        "n_positive": int(y.sum()),
        "calibrated": calibrate,
    }


def fit_statistical_model(
    df: pd.DataFrame,
    *,
    random_state: int = 42,
    calibrate: bool = True,
):
    """Fit production statistical model on all structural rows."""
    feature_cols = base_structural_feature_columns(df)
    pipe = build_statistical_pipeline(
        feature_columns=feature_cols,
        categorical_columns=[c for c in CATEGORICAL_COLUMNS if c in feature_cols],
        random_state=random_state,
    )
    if calibrate:
        cv = min(3, max(2, df["pdb_id"].nunique()))
        pipe = calibrate_estimator(pipe, cv=cv)
    pipe.fit(df[feature_cols], df["label"].astype(int))
    return pipe
