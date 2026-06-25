"""Cross-validated training with leakage control."""

from __future__ import annotations

import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold, StratifiedKFold

from pmhc_hotspot.ml.model import build_pipeline

FEATURE_COLUMNS = [
    "sasa",
    "hydrophobic_fraction",
    "polar_fraction",
    "protrusion",
    "curvature",
    "bulge",
    "hla_contacts",
    "peptide_contacts",
    "mutation_proximity",
    "confidence",
    "anchor_penalty",
    "chemical_score",
    "tcr_exposure_prior",
    "buried",
    "is_anchor",
    "peptide_length",
]
CATEGORICAL_COLUMNS = ["aa"]


def train_cv(
    df: pd.DataFrame,
    label_col: str = "label",
    model_type: str = "xgboost",
    n_splits: int = 5,
    random_state: int = 42,
) -> dict:
    feature_cols = [c for c in FEATURE_COLUMNS + CATEGORICAL_COLUMNS if c in df.columns]
    X = df[feature_cols]
    y = df[label_col].astype(int)

    if "pdb_id" in df.columns and df["pdb_id"].nunique() >= n_splits:
        splitter = GroupKFold(n_splits=n_splits)
        split_iter = splitter.split(X, y, groups=df["pdb_id"])
    else:
        splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
        split_iter = splitter.split(X, y)

    oof = pd.Series(index=df.index, dtype=float)
    fold_metrics = []

    for fold, (tr, te) in enumerate(split_iter, start=1):
        pipe = build_pipeline(
            feature_columns=feature_cols,
            categorical_columns=[c for c in CATEGORICAL_COLUMNS if c in feature_cols],
            model_type=model_type,
            random_state=random_state,
        )
        pipe.fit(X.iloc[tr], y.iloc[tr])
        prob = pipe.predict_proba(X.iloc[te])[:, 1]
        oof.iloc[te] = prob
        y_te = y.iloc[te]
        roc = roc_auc_score(y_te, prob) if len(set(y_te)) > 1 else float("nan")
        ap = average_precision_score(y_te, prob) if len(set(y_te)) > 1 else float("nan")
        fold_metrics.append({"fold": fold, "roc_auc": roc, "avg_precision": ap})

    overall = {
        "roc_auc": roc_auc_score(y, oof) if len(set(y)) > 1 else float("nan"),
        "avg_precision": average_precision_score(y, oof) if len(set(y)) > 1 else float("nan"),
    }
    return {
        "fold_metrics": fold_metrics,
        "overall": overall,
        "oof_predictions": oof.tolist(),
        "n_rows": len(df),
        "n_positive": int(y.sum()),
    }
