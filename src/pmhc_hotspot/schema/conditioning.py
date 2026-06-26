"""Design-conditioning schema — hotspot/patch YAML contract."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class ControlGroup(str, Enum):
    random = "random"
    exposed_only = "exposed_only"
    central_only = "central_only"
    predicted = "predicted"


class HotspotEntry(BaseModel):
    residue: int
    position: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    patch_id: Optional[str] = None
    chain: Optional[str] = None


class PatchEntry(BaseModel):
    id: str
    center: int
    radius: float = Field(gt=0.0, description="Angstroms")
    normal: List[float] = Field(min_length=3, max_length=3)
    members: List[int] = Field(min_length=1, description="1-based residue indices")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class DesignConditioning(BaseModel):
    """Standard hotspot/patch file for design backends."""

    schema_version: str = "1.0"
    target_id: str
    control_group: ControlGroup
    pdb_id: Optional[str] = None
    allele: Optional[str] = None
    peptide: Dict[str, str]
    hla_chains: List[str] = Field(default_factory=list)
    hotspots: List[HotspotEntry] = Field(default_factory=list)
    patches: List[PatchEntry] = Field(default_factory=list)
    rfdiffusion: Dict[str, Union[str, int]] = Field(default_factory=dict)
    proteinmpnn: Dict[str, Union[str, int]] = Field(default_factory=dict)
    af2: Dict[str, Union[str, int]] = Field(default_factory=dict)
    scoring_mode: Literal["deterministic", "statistical", "ml", "hybrid"] = "deterministic"
    model_bundle: Optional[str] = None

    model_config = {"extra": "forbid"}
