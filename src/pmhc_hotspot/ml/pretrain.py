"""Stage 1: public dataset pretraining (binding/affinity outcomes)."""

from __future__ import annotations

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from pmhc_hotspot.data.peptide_features import (
    POSITION_CATEGORICAL_COLUMNS,
    POSITION_FEATURE_COLUMNS,
    featurize_peptide_table,
)
from pmhc_hotspot.ml.model import build_base_estimator

PUBLIC_FEATURE_COLUMNS = [
    "peptide_length",
    "hydrophobic_frac",
    "aromatic_frac",
    "positive_frac",
    "negative_frac",
    "mean_chemical_score",
    "max_chemical_score",
] + POSITION_FEATURE_COLUMNS
PUBLIC_CATEGORICAL = ["allele"] + POSITION_CATEGORICAL_COLUMNS


def build_public_pretrain_pipeline(
    feature_columns: list[str],
    categorical_columns: list[str] | None = None,
    model_type: str = "logistic",
    random_state: int = 42,
) -> Pipeline:
    categorical_columns = categorical_columns or []
    numeric_columns = [c for c in feature_columns if c not in categorical_columns]
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="median")),
                        ("scale", StandardScaler()),
                    ]
                ),
                numeric_columns,
            ),
            (
                "cat",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_columns,
            ),
        ],
        remainder="drop",
    )
    return Pipeline(
        [
            ("preprocess", preprocessor),
            ("model", build_base_estimator(model_type, random_state=random_state)),
        ]
    )


def prepare_public_training_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Featurize and validate a combined public dataset."""
    return featurize_peptide_table(df)


def train_public_pretrain(
    df: pd.DataFrame,
    *,
    feature_cols: list[str] | None = None,
    group_col: str = "group_id",
    label_col: str = "label",
    model_type: str = "logistic",
    n_splits: int = 5,
    random_state: int = 42,
) -> dict:
    """
    Cross-validate public pretraining with StratifiedGroupKFold.

    Public binding/affinity labels are a pretraining signal only — not
    residue-level TCR-contact truth.
    """
    frame = prepare_public_training_frame(df)
    feature_cols = feature_cols or [
        c for c in PUBLIC_FEATURE_COLUMNS + PUBLIC_CATEGORICAL if c in frame.columns
    ]
    X = frame[feature_cols].copy()
    y = frame[label_col].astype(int)
    groups = frame[group_col].astype(str)

    if y.nunique() < 2:
        raise ValueError("Public pretraining requires both positive and negative labels")

    sgkf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    oof = pd.Series(index=frame.index, dtype=float)
    fold_metrics = []

    for fold, (tr, te) in enumerate(sgkf.split(X, y, groups), start=1):
        pipe = build_public_pretrain_pipeline(
            feature_columns=feature_cols,
            categorical_columns=[c for c in PUBLIC_CATEGORICAL if c in feature_cols],
            model_type=model_type,
            random_state=random_state,
        )
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
                "n_train": int(len(tr)),
                "n_test": int(len(te)),
            }
        )

    return {
        "stage": "public_pretrain",
        "oof": oof.tolist(),
        "fold_metrics": fold_metrics,
        "roc_auc": roc_auc_score(y, oof),
        "avg_precision": average_precision_score(y, oof),
        "n_rows": len(frame),
        "n_positive": int(y.sum()),
        "class_balance": float(y.mean()),
        "feature_columns": feature_cols,
        "disclaimer": (
            "Public binding labels are pretraining signal only; "
            "not equivalent to residue-level TCR-contact truth."
        ),
    }


def fit_public_pretrain_model(
    df: pd.DataFrame,
    *,
    model_type: str = "logistic",
    random_state: int = 42,
) -> tuple[Pipeline, pd.DataFrame]:
    """Fit final stage-1 model on all public data (for fine-tuning feature generation)."""
    frame = prepare_public_training_frame(df)
    feature_cols = [c for c in PUBLIC_FEATURE_COLUMNS + PUBLIC_CATEGORICAL if c in frame.columns]
    pipe = build_public_pretrain_pipeline(
        feature_columns=feature_cols,
        categorical_columns=[c for c in PUBLIC_CATEGORICAL if c in frame.columns],
        model_type=model_type,
        random_state=random_state,
    )
    pipe.fit(frame[feature_cols], frame["label"].astype(int))
    return pipe, frame
