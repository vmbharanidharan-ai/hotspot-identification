"""Stage 2: structural fine-tuning on residue-level TCR-contact labels."""

from __future__ import annotations

import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold

from pmhc_hotspot.data.peptide_features import featurize_peptide_table
from pmhc_hotspot.ml.model import build_pipeline
from pmhc_hotspot.ml.pretrain import PUBLIC_CATEGORICAL, PUBLIC_FEATURE_COLUMNS
from pmhc_hotspot.ml.train import CATEGORICAL_COLUMNS, FEATURE_COLUMNS


def attach_pretrain_probabilities(structural_df: pd.DataFrame, pretrained_model) -> pd.DataFrame:
    """
    Add peptide-level pretrain probability as a residue feature.

    Broadcasts one probability per peptide across all residue rows.
    """
    if "peptide" not in structural_df.columns:
        raise ValueError("Structural frame must include a peptide column")

    unique = structural_df[["peptide", "allele"]].drop_duplicates()
    pep_rows = []
    for _, row in unique.iterrows():
        pep_rows.append(
            {
                "peptide": row["peptide"],
                "allele": row["allele"],
                "label": 0,
                "source": "STRUCTURAL",
                "group_id": row["peptide"],
            }
        )
    public_like = featurize_peptide_table(pd.DataFrame(pep_rows))
    feature_cols = [c for c in PUBLIC_FEATURE_COLUMNS + PUBLIC_CATEGORICAL if c in public_like.columns]
    probs = pretrained_model.predict_proba(public_like[feature_cols])[:, 1]
    prob_map = dict(zip(public_like["peptide"], probs))

    out = structural_df.copy()
    out["pretrain_prob"] = out["peptide"].map(prob_map).fillna(0.5)
    return out


def fine_tune_structural(
    df: pd.DataFrame,
    *,
    label_col: str = "label",
    model_type: str = "logistic",
    n_splits: int = 5,
    random_state: int = 42,
    use_pretrain_feature: bool = False,
) -> dict:
    """
    Fine-tune on curated structural residue labels.

    Groups by PDB/complex ID to prevent leakage. Keeps structural benchmark
    splits separate from public pretraining data by design.
    """
    feature_cols = [c for c in FEATURE_COLUMNS + CATEGORICAL_COLUMNS if c in df.columns]
    if use_pretrain_feature and "pretrain_prob" in df.columns:
        feature_cols = feature_cols + ["pretrain_prob"]

    X = df[feature_cols]
    y = df[label_col].astype(int)

    if "pdb_id" not in df.columns:
        raise ValueError("Structural fine-tuning requires pdb_id for grouped CV")

    groups = df["pdb_id"].astype(str)
    if y.nunique() > 1 and groups.nunique() >= n_splits:
        splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
        split_iter = splitter.split(X, y, groups)
    else:
        splitter = GroupKFold(n_splits=min(n_splits, groups.nunique()))
        split_iter = splitter.split(X, y, groups)

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
        fold_metrics.append(
            {
                "fold": fold,
                "roc_auc": roc_auc_score(y_te, prob) if y_te.nunique() > 1 else float("nan"),
                "avg_precision": average_precision_score(y_te, prob)
                if y_te.nunique() > 1
                else float("nan"),
            }
        )

    length_strata = {}
    if "peptide_length" in df.columns:
        for length, sub_idx in df.groupby("peptide_length").groups.items():
            sub_y = y.loc[list(sub_idx)]
            sub_oof = oof.loc[list(sub_idx)]
            if sub_y.nunique() > 1:
                length_strata[int(length)] = {
                    "roc_auc": roc_auc_score(sub_y, sub_oof),
                    "n": int(len(sub_idx)),
                }

    return {
        "stage": "structural_finetune",
        "fold_metrics": fold_metrics,
        "overall": {
            "roc_auc": roc_auc_score(y, oof) if y.nunique() > 1 else float("nan"),
            "avg_precision": average_precision_score(y, oof) if y.nunique() > 1 else float("nan"),
        },
        "by_peptide_length": length_strata,
        "oof_predictions": oof.tolist(),
        "n_rows": len(df),
        "n_positive": int(y.sum()),
        "use_pretrain_feature": use_pretrain_feature,
        "disclaimer": (
            "Structural labels are TCR-contact proxies for hotspot prioritization, "
            "not direct immunogenicity prediction."
        ),
    }


def fit_structural_model(
    df: pd.DataFrame,
    *,
    model_type: str = "logistic",
    random_state: int = 42,
    use_pretrain_feature: bool = False,
):
    feature_cols = [c for c in FEATURE_COLUMNS + CATEGORICAL_COLUMNS if c in df.columns]
    if use_pretrain_feature and "pretrain_prob" in df.columns:
        feature_cols = feature_cols + ["pretrain_prob"]
    pipe = build_pipeline(
        feature_columns=feature_cols,
        categorical_columns=[c for c in CATEGORICAL_COLUMNS if c in feature_cols],
        model_type=model_type,
        random_state=random_state,
    )
    pipe.fit(df[feature_cols], df["label"].astype(int))
    return pipe
