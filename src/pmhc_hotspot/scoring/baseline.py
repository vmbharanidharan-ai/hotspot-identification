"""Deterministic baseline hotspot scoring."""

from __future__ import annotations

from pmhc_hotspot.constants import DEFAULT_WEIGHTS
from pmhc_hotspot.features.allele_rules import AnchorFilter


class HotspotScorer:
    """
    Deterministic, explainable residue scoring.

    All input features must be normalized to [0, 1] before scoring.
    Anchor suppression is multiplicative (strongest when buried).
    """

    def __init__(self, allele: str | None = None, weights: dict[str, float] | None = None):
        self.weights = dict(weights or DEFAULT_WEIGHTS)
        self.anchor_filter = AnchorFilter(allele)

    def score_residue(
        self,
        features: dict[str, float],
        position_1based: int,
        peptide_length: int,
        *,
        buried: bool,
    ) -> tuple[float, dict[str, float]]:
        """
        Compute bounded score in [0, 1] and per-component explanation.

        Returns (score, explanation_dict).
        """
        w = self.weights
        explanation = {
            "sasa": w["sasa"] * features["sasa"],
            "protrusion": w["protrusion"] * features["protrusion"],
            "curvature": w["curvature"] * features["curvature"],
            "bulge": w["bulge"] * features["bulge"],
            "mutation": w["mutation"] * features["mutation_proximity"],
            "low_hla_contact": w["low_hla_contact"] * (1.0 - features["hla_contact_norm"]),
            "tcr_exposure": w["tcr_exposure"] * features["tcr_exposure_prior"],
            "chemical": w["chemical"] * features["chemical_norm"],
            "confidence": w["confidence"] * features["confidence"],
        }

        base = sum(explanation.values())
        anchor_penalty = self.anchor_filter.penalty(
            position_1based,
            peptide_length,
            buried=buried,
            relative_sasa=features["sasa"],
        )
        explanation["anchor_penalty"] = -anchor_penalty * base

        final = max(0.0, min(1.0, base * (1.0 - anchor_penalty)))
        return final, explanation
