"""Design control strategies for Tier 2.5 validation (Phase 2.1)."""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from pmhc_hotspot.api import HotspotPredictor
from pmhc_hotspot.features.positioning import PeptideResidueMap
from pmhc_hotspot.io import StructureLoader, chain_ca_residues, get_chain


class DesignControlStrategy(ABC):
    """Select peptide residue indices (1-based) for design conditioning."""

    @abstractmethod
    def select_residues(
        self,
        pdb_file: str | Path,
        peptide_chain: str,
        *,
        n_select: int = 5,
        allele: Optional[str] = None,
        seed: int = 42,
    ) -> List[int]:
        pass


class HotspotStrategy(DesignControlStrategy):
    """Top-N residues by pmhc-hotspot score."""

    def __init__(self, scoring_mode: str = "hybrid"):
        self.scoring_mode = scoring_mode

    def select_residues(self, pdb_file, peptide_chain, *, n_select=5, allele=None, seed=42):
        predictor = HotspotPredictor(allele=allele, peptide_chain=peptide_chain, scoring_mode=self.scoring_mode)
        result = predictor.predict(pdb_file)
        ranked = sorted(result.residue_scores, key=lambda r: r.score, reverse=True)
        return [r.position_index + 1 for r in ranked[:n_select]]


class RandomStrategy(DesignControlStrategy):
    """Random eligible peptide residues."""

    def select_residues(self, pdb_file, peptide_chain, *, n_select=5, allele=None, seed=42):
        structure = StructureLoader().load(pdb_file)
        prm = PeptideResidueMap(get_chain(structure, peptide_chain))
        rng = random.Random(seed)
        indices = list(range(1, prm.length + 1))
        rng.shuffle(indices)
        return sorted(indices[:n_select])


class ExposedResidueStrategy(DesignControlStrategy):
    """Highest relative SASA residues."""

    def select_residues(self, pdb_file, peptide_chain, *, n_select=5, allele=None, seed=42):
        predictor = HotspotPredictor(allele=allele, peptide_chain=peptide_chain, scoring_mode="deterministic")
        result = predictor.predict(pdb_file, select_hotspots=False)
        ranked = sorted(result.residue_scores, key=lambda r: (-r.relative_sasa, -r.score))
        return [r.position_index + 1 for r in ranked[:n_select]]


class CentralResidueStrategy(DesignControlStrategy):
    """Central bulge positions P3–P8."""

    def select_residues(self, pdb_file, peptide_chain, *, n_select=5, allele=None, seed=42):
        predictor = HotspotPredictor(allele=allele, peptide_chain=peptide_chain, scoring_mode="deterministic")
        result = predictor.predict(pdb_file, select_hotspots=False)
        central = [r for r in result.residue_scores if 3 <= r.position_index + 1 <= 8]
        ranked = sorted(central, key=lambda r: (-r.bulge, -r.score))
        picks = [r.position_index + 1 for r in ranked[:n_select]]
        if len(picks) < n_select:
            extra = sorted(result.residue_scores, key=lambda r: r.score, reverse=True)
            for r in extra:
                idx = r.position_index + 1
                if idx not in picks:
                    picks.append(idx)
                if len(picks) >= n_select:
                    break
        return picks[:n_select]


class AnchorStrategy(DesignControlStrategy):
    """Allele-specific anchor positions from allele_rules."""

    def select_residues(self, pdb_file, peptide_chain, *, n_select=5, allele=None, seed=42):
        from pmhc_hotspot.features.allele_rules import get_anchor_positions

        structure = StructureLoader().load(pdb_file)
        prm = PeptideResidueMap(get_chain(structure, peptide_chain))
        anchors = sorted(get_anchor_positions(allele, prm.length))
        return anchors[:n_select] if anchors else list(range(1, min(n_select, prm.length) + 1))


STRATEGY_REGISTRY = {
    "hotspot": HotspotStrategy,
    "predicted": HotspotStrategy,
    "random": RandomStrategy,
    "exposed_only": ExposedResidueStrategy,
    "exposed": ExposedResidueStrategy,
    "central_only": CentralResidueStrategy,
    "central": CentralResidueStrategy,
    "anchor": AnchorStrategy,
}


def get_strategy(name: str, **kwargs) -> DesignControlStrategy:
    cls = STRATEGY_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown strategy: {name}. Choose from {sorted(STRATEGY_REGISTRY)}")
    return cls(**kwargs)
