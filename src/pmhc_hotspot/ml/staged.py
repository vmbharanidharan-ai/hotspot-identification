"""Two-stage training orchestration: public pretrain → structural fine-tune."""

from __future__ import annotations

import pandas as pd

from pmhc_hotspot.ml.calibration import learn_hybrid_alpha
from pmhc_hotspot.ml.fine_tune import (
    attach_pretrain_probabilities,
    fine_tune_structural,
    fit_structural_model,
    structural_feature_columns,
)
from pmhc_hotspot.ml.persistence import StagedModelBundle
from pmhc_hotspot.ml.pretrain import fit_public_pretrain_model, train_public_pretrain
from pmhc_hotspot.ml.statistical import (
    attach_stat_probabilities,
    base_structural_feature_columns,
    fit_statistical_model,
    train_statistical_cv,
)


def run_staged_training(
    public_df: pd.DataFrame,
    structural_df: pd.DataFrame,
    *,
    model_type: str = "logistic",
    n_splits: int = 5,
    random_state: int = 42,
    contact_mode: str = "standard",
    use_pretrain: bool = True,
    hybrid_alpha: float | None = None,
    calibrate: bool = True,
) -> dict:
    """
    Full staged recipe:
    1) optional public pretraining (IEDB/ATLAS)
    2) statistical elastic-net logistic on structural TCR-contact labels
    3) nonlinear ML fine-tune with stat_prob (+ optional pretrain_prob)
    4) learned hybrid blend weight (stat vs ML) from OOF predictions
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

    statistical_cv = train_statistical_cv(
        structural_df,
        n_splits=n_splits,
        random_state=random_state,
        calibrate=calibrate,
    )
    statistical_model = fit_statistical_model(
        structural_df, random_state=random_state, calibrate=calibrate
    )
    structural_aug = attach_stat_probabilities(structural_df, statistical_model)

    if use_pretrain and pretrained_model is not None:
        structural_aug = attach_pretrain_probabilities(structural_aug, pretrained_model)

    finetune_cv = fine_tune_structural(
        structural_aug,
        model_type=model_type,
        n_splits=n_splits,
        random_state=random_state,
        use_pretrain_feature=use_pretrain,
        use_stat_feature=True,
        calibrate=calibrate,
    )
    final_model = fit_structural_model(
        structural_aug,
        model_type=model_type,
        random_state=random_state,
        use_pretrain_feature=use_pretrain,
        use_stat_feature=True,
        calibrate=calibrate,
    )

    stat_oof = statistical_cv["oof_predictions"]
    ml_oof = pd.Series(finetune_cv["oof_predictions"], index=structural_aug.index)
    learned_alpha = (
        hybrid_alpha
        if hybrid_alpha is not None
        else learn_hybrid_alpha(
            stat_oof,
            ml_oof,
            structural_aug["label"].astype(int),
        )
    )

    stat_feature_cols = base_structural_feature_columns(structural_df)
    ml_feature_cols = structural_feature_columns(
        structural_aug,
        use_stat_feature=True,
        use_pretrain_feature=use_pretrain,
    )
    bundle = StagedModelBundle(
        final_model=final_model,
        feature_columns=ml_feature_cols,
        categorical_columns=[c for c in ["aa"] if c in ml_feature_cols],
        model_type=model_type,
        use_pretrain_feature=use_pretrain,
        use_stat_feature=True,
        contact_mode=contact_mode,
        pretrained_model=pretrained_model,
        statistical_model=statistical_model,
        stat_feature_columns=stat_feature_cols,
        hybrid_alpha=learned_alpha,
        calibrated=calibrate,
    )

    return {
        "pretrain_cv": pretrain_cv,
        "statistical_cv": statistical_cv,
        "finetune_cv": finetune_cv,
        "pretrained_model": pretrained_model,
        "statistical_model": statistical_model,
        "final_model": final_model,
        "model_bundle": bundle,
        "hybrid_alpha": learned_alpha,
        "n_public_rows": len(public_df) if use_pretrain else 0,
        "n_structural_rows": len(structural_df),
        "contact_mode": contact_mode,
        "use_pretrain": use_pretrain,
        "calibrated": calibrate,
    }
