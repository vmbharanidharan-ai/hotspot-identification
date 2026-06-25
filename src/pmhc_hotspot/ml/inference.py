"""Residue-level ML inference helpers."""

from __future__ import annotations

import pandas as pd

from pmhc_hotspot.ml.fine_tune import attach_pretrain_probabilities
from pmhc_hotspot.ml.hybrid import HybridScorer
from pmhc_hotspot.ml.persistence import StagedModelBundle
from pmhc_hotspot.ml.statistical import attach_stat_probabilities
from pmhc_hotspot.ml.train import CATEGORICAL_COLUMNS, FEATURE_COLUMNS
from pmhc_hotspot.types import PredictionResult, ResidueScore

SCORING_MODES = ("deterministic", "statistical", "ml", "hybrid")


def residue_scores_to_frame(prediction: PredictionResult) -> pd.DataFrame:
    """Convert a PredictionResult to structural ML feature rows."""
    rows = []
    for r in prediction.residue_scores:
        rows.append(
            {
                "peptide": prediction.peptide_sequence,
                "allele": prediction.allele,
                "peptide_length": prediction.peptide_length,
                "position": r.position,
                "aa": r.aa,
                "sasa": r.relative_sasa,
                "hydrophobic_fraction": r.hydrophobic_fraction,
                "polar_fraction": r.polar_fraction,
                "protrusion": r.protrusion,
                "curvature": r.curvature,
                "bulge": r.bulge,
                "hla_contacts": r.hla_contacts,
                "peptide_contacts": r.peptide_contacts,
                "mutation_proximity": r.mutation_proximity,
                "confidence": r.confidence,
                "anchor_penalty": r.anchor_penalty,
                "chemical_score": r.chemical_score,
                "tcr_exposure_prior": r.tcr_exposure_prior,
                "buried": int(r.is_buried),
                "is_anchor": int(r.is_anchor),
            }
        )
    return pd.DataFrame(rows)


def _prepare_ml_frame(prediction: PredictionResult, bundle: StagedModelBundle) -> pd.DataFrame:
    frame = residue_scores_to_frame(prediction)
    if bundle.statistical_model is not None:
        frame = attach_stat_probabilities(frame, bundle.statistical_model)
    elif bundle.use_stat_feature and bundle.final_model is not None:
        # Legacy bundles: fall back to final model for stat_prob if missing
        pass
    if bundle.use_pretrain_feature and bundle.pretrained_model is not None:
        frame = attach_pretrain_probabilities(frame, bundle.pretrained_model)
    return frame


def predict_statistical_probabilities(
    prediction: PredictionResult,
    bundle: StagedModelBundle,
) -> pd.Series:
    """Return calibrated statistical-layer contact probabilities."""
    if bundle.statistical_model is None:
        raise ValueError("Bundle has no statistical_model; use scoring_mode='ml' or retrain")
    frame = residue_scores_to_frame(prediction)
    stat_cols = bundle.stat_feature_columns or [
        c for c in FEATURE_COLUMNS + CATEGORICAL_COLUMNS if c in frame.columns
    ]
    probs = bundle.statistical_model.predict_proba(frame[stat_cols])[:, 1]
    return pd.Series(probs, index=frame.index)


def predict_residue_probabilities(
    prediction: PredictionResult,
    bundle: StagedModelBundle,
) -> pd.Series:
    """Return ML-layer contact probabilities aligned to residue_scores order."""
    frame = _prepare_ml_frame(prediction, bundle)
    feature_cols = [c for c in bundle.feature_columns if c in frame.columns]
    probs = bundle.final_model.predict_proba(frame[feature_cols])[:, 1]
    return pd.Series(probs, index=frame.index)


def blend_residue_scores(
    residue_scores: list[ResidueScore],
    ml_probs: pd.Series | None,
    *,
    scoring_mode: str,
    stat_probs: pd.Series | None = None,
    hybrid_alpha: float = 0.5,
    heuristic_scores: pd.Series | None = None,
) -> list[tuple[ResidueScore, float]]:
    """
    Pair residues with ranking scores.

    - deterministic: hand-weighted heuristic score
    - statistical: elastic-net P(contact)
    - ml: nonlinear ML P(contact)
    - hybrid: α·P_stat + (1−α)·P_ml (falls back to heuristic+ml for legacy bundles)
    """
    if scoring_mode not in SCORING_MODES:
        raise ValueError(f"scoring_mode must be one of {SCORING_MODES}")

    hybrid = HybridScorer(alpha=hybrid_alpha)
    ranked: list[tuple[ResidueScore, float]] = []
    for i, residue in enumerate(residue_scores):
        det = float(heuristic_scores.iloc[i]) if heuristic_scores is not None else float(residue.score)
        stat = float(stat_probs.iloc[i]) if stat_probs is not None and i < len(stat_probs) else det
        ml = float(ml_probs.iloc[i]) if ml_probs is not None and i < len(ml_probs) else 0.5

        if scoring_mode == "ml":
            rank_score = ml
        elif scoring_mode == "statistical":
            rank_score = stat
        elif scoring_mode == "hybrid":
            if stat_probs is not None and ml_probs is not None:
                rank_score = float(hybrid.combine([stat], [ml])[0])
            else:
                rank_score = float(hybrid.combine([det], [ml])[0])
        else:
            rank_score = det
        ranked.append((residue, rank_score))
    return ranked


def order_positions_by_score(
    prediction: PredictionResult,
    *,
    scoring_mode: str = "deterministic",
    bundle: StagedModelBundle | None = None,
    hybrid_alpha: float | None = None,
) -> list[str]:
    """Return P-position labels ordered best-first for benchmarking."""
    if scoring_mode == "deterministic" or bundle is None:
        ordered = sorted(prediction.residue_scores, key=lambda r: r.score, reverse=True)
        return [r.position for r in ordered]

    alpha = bundle.hybrid_alpha if hybrid_alpha is None else hybrid_alpha
    stat_probs = None
    if scoring_mode in {"statistical", "hybrid"} and bundle.statistical_model is not None:
        stat_probs = predict_statistical_probabilities(prediction, bundle)

    ml_probs = None
    if scoring_mode in {"ml", "hybrid"}:
        ml_probs = predict_residue_probabilities(prediction, bundle)

    ranked = blend_residue_scores(
        prediction.residue_scores,
        ml_probs,
        scoring_mode=scoring_mode,
        stat_probs=stat_probs,
        hybrid_alpha=alpha,
    )
    ranked.sort(key=lambda item: (-item[1], item[0].position_index))
    return [r.position for r, _ in ranked]
