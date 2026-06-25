"""Two-stage training orchestration: public pretrain → structural fine-tune."""

from __future__ import annotations

import pandas as pd

from pmhc_hotspot.ml.fine_tune import (
    attach_pretrain_probabilities,
    fine_tune_structural,
    fit_structural_model,
)
from pmhc_hotspot.ml.persistence import StagedModelBundle
from pmhc_hotspot.ml.pretrain import fit_public_pretrain_model, train_public_pretrain
from pmhc_hotspot.ml.train import CATEGORICAL_COLUMNS, FEATURE_COLUMNS


def _structural_feature_columns(structural_df: pd.DataFrame, *, use_pretrain: bool) -> list[str]:
    cols = [c for c in FEATURE_COLUMNS + CATEGORICAL_COLUMNS if c in structural_df.columns]
    if use_pretrain and "pretrain_prob" in structural_df.columns and "pretrain_prob" not in cols:
        cols = cols + ["pretrain_prob"]
    return cols


def run_staged_training(
    public_df: pd.DataFrame,
    structural_df: pd.DataFrame,
    *,
    model_type: str = "logistic",
    n_splits: int = 5,
    random_state: int = 42,
    contact_mode: str = "standard",
    use_pretrain: bool = True,
    hybrid_alpha: float = 0.6,
) -> dict:
    """
    Full two-stage recipe:
    1) public pretraining on binding/affinity outcomes
    2) structural fine-tuning on residue-level TCR-contact labels
  """
    if use_pretrain and public_df.empty:
        raise ValueError("Public pretraining dataframe is empty")
    if structural_df.empty:
        raise ValueError("Structural fine-tuning dataframe is empty")

    pretrained_model = None
    pretrain_cv = None
    if use_pretrain:
        pretrain_cv = train_public_pretrain(
            public_df,
            model_type=model_type,
            n_splits=n_splits,
            random_state=random_state,
        )
        pretrained_model, _ = fit_public_pretrain_model(
            public_df, model_type=model_type, random_state=random_state
        )
        structural_aug = attach_pretrain_probabilities(structural_df, pretrained_model)
    else:
        structural_aug = structural_df.copy()

    finetune_cv = fine_tune_structural(
        structural_aug,
        model_type=model_type,
        n_splits=n_splits,
        random_state=random_state,
        use_pretrain_feature=use_pretrain,
    )
    final_model = fit_structural_model(
        structural_aug,
        model_type=model_type,
        random_state=random_state,
        use_pretrain_feature=use_pretrain,
    )

    feature_cols = _structural_feature_columns(structural_aug, use_pretrain=use_pretrain)
    bundle = StagedModelBundle(
        final_model=final_model,
        feature_columns=feature_cols,
        categorical_columns=[c for c in CATEGORICAL_COLUMNS if c in feature_cols],
        model_type=model_type,
        use_pretrain_feature=use_pretrain,
        contact_mode=contact_mode,
        pretrained_model=pretrained_model,
        hybrid_alpha=hybrid_alpha,
    )

    return {
        "pretrain_cv": pretrain_cv,
        "finetune_cv": finetune_cv,
        "pretrained_model": pretrained_model,
        "final_model": final_model,
        "model_bundle": bundle,
        "n_public_rows": len(public_df) if use_pretrain else 0,
        "n_structural_rows": len(structural_df),
        "contact_mode": contact_mode,
        "use_pretrain": use_pretrain,
    }
