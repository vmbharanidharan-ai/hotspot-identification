"""Canonical data contracts for the binder-conditioning pipeline."""

from pmhc_hotspot.schema.conditioning import (
    DesignConditioning,
    HotspotEntry,
    PatchEntry,
)
from pmhc_hotspot.schema.design_eval import (
    ControlComparison,
    DesignCandidateMetrics,
    DesignEvalReport,
)
from pmhc_hotspot.schema.examples import (
    ComplexExample,
    ExampleLabels,
    ExampleProvenance,
    ExampleSplit,
    ResidueFeatures,
)

__all__ = [
    "ComplexExample",
    "ExampleLabels",
    "ExampleProvenance",
    "ExampleSplit",
    "ResidueFeatures",
    "DesignConditioning",
    "HotspotEntry",
    "PatchEntry",
    "DesignEvalReport",
    "DesignCandidateMetrics",
    "ControlComparison",
]
