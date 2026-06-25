"""Dataclasses for hotspot prediction outputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ResidueScore:
    """Per-residue hotspot score with explainable components."""

    chain_id: str
    resseq: int
    icode: str = ""
    aa: str = "X"
    position: str = ""  # e.g. P4
    position_index: int = 0  # 0-based peptide index
    normalized_position: float = 0.0  # 0 = N-term, 1 = C-term
    score: float = 0.0
    sasa: float = 0.0
    relative_sasa: float = 0.0
    hydrophobic_sasa: float = 0.0
    polar_sasa: float = 0.0
    hydrophobic_fraction: float = 0.0
    polar_fraction: float = 0.0
    protrusion: float = 0.0
    curvature: float = 0.0
    bulge: float = 0.0
    hla_contacts: int = 0
    peptide_contacts: int = 0
    mutation_proximity: float = 0.0
    confidence: float = 1.0
    anchor_penalty: float = 0.0
    chemical_score: float = 0.0
    tcr_exposure_prior: float = 0.0
    is_anchor: bool = False
    is_buried: bool = False
    low_confidence: bool = False
    eligible_for_hotspot: bool = True
    explanation: dict[str, float] = field(default_factory=dict)

    @property
    def rfdiffusion_token(self) -> str:
        """RFdiffusion ppi.hotspot_res format: chain + residue number."""
        return f"{self.chain_id}{self.resseq}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HotspotPatch:
    """Contiguous peptide surface patch for RFdiffusion targeting."""

    positions: list[str]
    residues: list[ResidueScore]
    patch_score: float
    patch_id: int = 0

    @property
    def rfdiffusion_tokens(self) -> list[str]:
        return [r.rfdiffusion_token for r in self.residues]

    @property
    def rfdiffusion_hotspot_res(self) -> str:
        return ",".join(self.rfdiffusion_tokens)

    def to_dict(self) -> dict[str, Any]:
        return {
            "patch_id": self.patch_id,
            "positions": self.positions,
            "patch_score": self.patch_score,
            "rfdiffusion_hotspot_res": self.rfdiffusion_hotspot_res,
            "residues": [r.to_dict() for r in self.residues],
        }


@dataclass(frozen=True)
class PredictionResult:
    """Full hotspot prediction output."""

    allele: str | None
    peptide_chain_id: str
    hla_chain_ids: list[str]
    peptide_sequence: str
    peptide_length: int
    residue_scores: list[ResidueScore]
    hotspots: list[ResidueScore]
    patches: list[HotspotPatch]
    rfdiffusion_hotspot_res: str
    contig_template: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allele": self.allele,
            "peptide_chain_id": self.peptide_chain_id,
            "hla_chain_ids": self.hla_chain_ids,
            "peptide_sequence": self.peptide_sequence,
            "peptide_length": self.peptide_length,
            "rfdiffusion_hotspot_res": self.rfdiffusion_hotspot_res,
            "contig_template": self.contig_template,
            "metadata": self.metadata,
            "residue_scores": [r.to_dict() for r in self.residue_scores],
            "hotspots": [r.to_dict() for r in self.hotspots],
            "patches": [p.to_dict() for p in self.patches],
        }
