"""Tests for ML inference ranking helpers."""

import pandas as pd

from pmhc_hotspot.ml.inference import blend_residue_scores, order_positions_by_score
from pmhc_hotspot.ml.persistence import StagedModelBundle
from pmhc_hotspot.types import PredictionResult, ResidueScore


class _DummyModel:
    def predict_proba(self, X):
        import numpy as np

        # Higher ML score for later rows
        probs = np.linspace(0.2, 0.9, len(X))
        return np.column_stack([1 - probs, probs])


def _residue(position_index: int, score: float) -> ResidueScore:
    return ResidueScore(
        chain_id="C",
        resseq=position_index + 1,
        icode="",
        aa="L",
        position=f"P{position_index + 1}",
        position_index=position_index,
        normalized_position=0.5,
        score=score,
        sasa=40.0,
        relative_sasa=0.5,
        protrusion=1.0,
        curvature=0.5,
        bulge=0.5,
        hla_contacts=2,
        peptide_contacts=1,
        mutation_proximity=0.0,
        confidence=0.9,
        anchor_penalty=0.0,
        chemical_score=5.0,
        tcr_exposure_prior=0.9,
        is_anchor=False,
        is_buried=False,
        low_confidence=False,
        eligible_for_hotspot=True,
        explanation="test",
    )


def _prediction(residues: list[ResidueScore]) -> PredictionResult:
    return PredictionResult(
        allele="HLA-A*02:01",
        peptide_chain_id="C",
        hla_chain_ids=["A"],
        peptide_sequence="L" * len(residues),
        peptide_length=len(residues),
        residue_scores=residues,
        hotspots=[],
        patches=[],
        rfdiffusion_hotspot_res="",
        contig_template="",
        metadata={},
    )


def test_ml_mode_orders_by_model_probability():
    residues = [_residue(i, 1.0 - i * 0.1) for i in range(5)]
    bundle = StagedModelBundle(
        final_model=_DummyModel(),
        feature_columns=[
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
            "aa",
        ],
        categorical_columns=["aa"],
        model_type="logistic",
        use_pretrain_feature=False,
    )
    ordered = order_positions_by_score(
        _prediction(residues), scoring_mode="ml", bundle=bundle
    )
    assert ordered[0] == "P5"


def test_hybrid_blend_between_deterministic_and_ml():
    residues = [_residue(0, 0.9), _residue(1, 0.1)]
    ml_probs = pd.Series([0.1, 0.9])
    ranked = blend_residue_scores(residues, ml_probs, scoring_mode="hybrid", hybrid_alpha=0.3)
    scores = {r.position: s for r, s in ranked}
    assert scores["P2"] > scores["P1"]
