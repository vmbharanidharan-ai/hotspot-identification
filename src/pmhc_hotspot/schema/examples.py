"""Canonical per-complex example schema (internal contract)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ExampleSplit(str, Enum):
    train = "train"
    val = "val"
    test = "test"
    holdout = "holdout"


class ExampleProvenance(BaseModel):
    pdb_id: str
    source: str = "pdb"
    structure_path: str
    manifest_path: Optional[str] = None
    downloaded_at: Optional[str] = None
    parser_version: str = "0.1.0"
    notes: str = ""


class ResidueFeatures(BaseModel):
    position: str
    position_index: int
    aa: str
    sasa: float = 0.0
    relative_sasa: float = 0.0
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
    buried: bool = False
    is_anchor: bool = False
    docking_contact_prior: Optional[float] = None


class ExampleLabels(BaseModel):
    contact_mode: str = "standard"
    tcr_contact_positions: List[str] = Field(default_factory=list)
    label_source: str = "computed_tcr_contacts"


class ComplexExample(BaseModel):
    """One pMHC structure as a training/eval example."""

    example_id: str
    allele: Optional[str] = None
    peptide_chain: str
    hla_chains: List[str]
    tcr_chains: List[str] = Field(default_factory=list)
    peptide_sequence: str
    peptide_length: int
    structure_path: str
    split: ExampleSplit = ExampleSplit.train
    provenance: ExampleProvenance
    residue_features: List[ResidueFeatures] = Field(default_factory=list)
    labels: Optional[ExampleLabels] = None
    extra: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("peptide_length")
    @classmethod
    def length_matches_sequence(cls, v: int, info) -> int:
        seq = (info.data or {}).get("peptide_sequence")
        if seq and len(seq) != v:
            raise ValueError(f"peptide_length {v} != len(sequence) {len(seq)}")
        return v

    model_config = {"extra": "forbid"}
