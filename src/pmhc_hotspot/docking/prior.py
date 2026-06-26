"""Geometry consensus docking contact priors (M3).

These are **feature priors only** — never used as supervised labels.
External docking wrappers (HADDOCK, etc.) can replace `geometry_consensus`
when wired; the output contract stays `docking_contact_prior` per residue.
"""

from __future__ import annotations

from typing import Dict, List

from pmhc_hotspot.docking.config import DockingPriorConfig
from pmhc_hotspot.scoring.calibration import minmax_normalize
from pmhc_hotspot.types import ResidueScore


def geometry_consensus_priors(
    residue_scores: List[ResidueScore],
    weights: Dict[str, float],
) -> List[float]:
    """
    Consensus contact prior in [0, 1] from structural geometry.

    Proxy for pose-ensemble contact frequency until fragment docking is wired.
    """
    if not residue_scores:
        return []

    norm_sasa = minmax_normalize([r.relative_sasa for r in residue_scores])
    norm_protrusion = minmax_normalize([r.protrusion for r in residue_scores])
    norm_bulge = minmax_normalize([r.bulge for r in residue_scores])
    norm_tcr = minmax_normalize([r.tcr_exposure_prior for r in residue_scores])
    norm_chem = minmax_normalize([r.chemical_score for r in residue_scores])

    priors: list[float] = []
    for j, residue in enumerate(residue_scores):
        if residue.is_buried:
            priors.append(0.0)
            continue
        prior = (
            weights.get("relative_sasa", 0.0) * norm_sasa[j]
            + weights.get("protrusion", 0.0) * norm_protrusion[j]
            + weights.get("bulge", 0.0) * norm_bulge[j]
            + weights.get("tcr_exposure_prior", 0.0) * norm_tcr[j]
            + weights.get("chemical_norm", 0.0) * norm_chem[j]
        )
        priors.append(min(1.0, max(0.0, prior)))
    return priors


def compute_docking_priors(
    residue_scores: List[ResidueScore],
    config: DockingPriorConfig,
) -> List[float]:
    if not config.enabled:
        return [0.0] * len(residue_scores)
    if config.method == "geometry_consensus":
        return geometry_consensus_priors(residue_scores, config.weights)
    raise ValueError(f"Unsupported docking prior method: {config.method}")
