"""Residue-level ML inference helpers."""

from __future__ import annotations

import pandas as pd

from pmhc_hotspot.ml.fine_tune import attach_pretrain_probabilities
from pmhc_hotspot.ml.hybrid import HybridScorer
from pmhc_hotspot.ml.persistence import StagedModelBundle
from pmhc_hotspot.ml.train import CATEGORICAL_COLUMNS, FEATURE_COLUMNS
from pmhc_hotspot.types import PredictionResult, ResidueScore


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


def predict_residue_probabilities(
    prediction: PredictionResult,
    bundle: StagedModelBundle,
) -> pd.Series:
    """Return ML contact probabilities aligned to prediction.residue_scores order."""
    frame = residue_scores_to_frame(prediction)
    feature_cols = [c for c in bundle.feature_columns if c in frame.columns]
    if bundle.use_pretrain_feature and bundle.pretrained_model is not None:
        frame = attach_pretrain_probabilities(frame, bundle.pretrained_model)
        if "pretrain_prob" in frame.columns and "pretrain_prob" not in feature_cols:
            feature_cols = feature_cols + ["pretrain_prob"]
    probs = bundle.final_model.predict_proba(frame[feature_cols])[:, 1]
    return pd.Series(probs, index=frame.index)


def blend_residue_scores(
    residue_scores: list[ResidueScore],
    ml_probs: pd.Series,
    *,
    scoring_mode: str,
    hybrid_alpha: float = 0.6,
) -> list[tuple[ResidueScore, float]]:
    """Pair residues with ranking scores for deterministic / ml / hybrid modes."""
    if scoring_mode not in {"deterministic", "ml", "hybrid"}:
        raise ValueError("scoring_mode must be deterministic, ml, or hybrid")

    ranked: list[tuple[ResidueScore, float]] = []
    hybrid = HybridScorer(alpha=hybrid_alpha)
    for i, residue in enumerate(residue_scores):
        det = float(residue.score)
        ml = float(ml_probs.iloc[i]) if i < len(ml_probs) else 0.5
        if scoring_mode == "ml":
            rank_score = ml
        elif scoring_mode == "hybrid":
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
    hybrid_alpha: float = 0.6,
) -> list[str]:
    """Return P-position labels ordered best-first for benchmarking."""
    if scoring_mode == "deterministic" or bundle is None:
        ordered = sorted(prediction.residue_scores, key=lambda r: r.score, reverse=True)
        return [r.position for r in ordered]

    ml_probs = predict_residue_probabilities(prediction, bundle)
    ranked = blend_residue_scores(
        prediction.residue_scores,
        ml_probs,
        scoring_mode=scoring_mode,
        hybrid_alpha=hybrid_alpha,
    )
    ranked.sort(key=lambda item: (-item[1], item[0].position_index))
    return [r.position for r, _ in ranked]
