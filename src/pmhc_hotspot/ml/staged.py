"""Two-stage training orchestration: public pretrain → structural fine-tune."""

from __future__ import annotations

import pandas as pd

from pmhc_hotspot.ml.fine_tune import (
    attach_pretrain_probabilities,
    fine_tune_structural,
    fit_structural_model,
)
from pmhc_hotspot.ml.pretrain import fit_public_pretrain_model, train_public_pretrain


def run_staged_training(
    public_df: pd.DataFrame,
    structural_df: pd.DataFrame,
    *,
    model_type: str = "logistic",
    n_splits: int = 5,
    random_state: int = 42,
) -> dict:
    """
    Full two-stage recipe:
    1) public pretraining on binding/affinity outcomes
    2) structural fine-tuning on residue-level TCR-contact labels
    """
    if public_df.empty:
        raise ValueError("Public pretraining dataframe is empty")
    if structural_df.empty:
        raise ValueError("Structural fine-tuning dataframe is empty")

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
    finetune_cv = fine_tune_structural(
        structural_aug,
        model_type=model_type,
        n_splits=n_splits,
        random_state=random_state,
        use_pretrain_feature=True,
    )
    final_model = fit_structural_model(
        structural_aug,
        model_type=model_type,
        random_state=random_state,
        use_pretrain_feature=True,
    )

    return {
        "pretrain_cv": pretrain_cv,
        "finetune_cv": finetune_cv,
        "pretrained_model": pretrained_model,
        "final_model": final_model,
        "n_public_rows": len(public_df),
        "n_structural_rows": len(structural_df),
    }
