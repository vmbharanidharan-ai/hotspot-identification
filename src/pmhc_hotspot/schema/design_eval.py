"""Downstream design validation report schema."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from pmhc_hotspot.schema.conditioning import ControlGroup


class DesignCandidateMetrics(BaseModel):
    candidate_id: str
    control_group: ControlGroup
    target_id: str
    seed: int
    backbone_path: Optional[str] = None
    sequence_path: Optional[str] = None
    interface_rmsd: Optional[float] = None
    interface_pae: Optional[float] = None
    interface_contacts: Optional[int] = None
    buried_surface_area: Optional[float] = None
    rosetta_interface_score: Optional[float] = None
    af2_plddt: Optional[float] = None
    af2_ipae: Optional[float] = None
    hotspot_contact_fraction: Optional[float] = None
    rank: Optional[int] = None


class ControlComparison(BaseModel):
    control_group: ControlGroup
    n_candidates: int
    primary_metric: str
    mean_primary: Optional[float] = None
    median_primary: Optional[float] = None
    best_primary: Optional[float] = None


class DesignEvalReport(BaseModel):
    schema_version: str = "1.0"
    target_id: str
    primary_metric: str = "af2_ipae"
    higher_is_better: bool = False
    comparisons: List[ControlComparison] = Field(default_factory=list)
    candidates: List[DesignCandidateMetrics] = Field(default_factory=list)
    predicted_beats_controls: List[ControlGroup] = Field(default_factory=list)
    gatekeeper_verdict: Optional[str] = None
    notes: str = ""

    model_config = {"extra": "forbid"}
