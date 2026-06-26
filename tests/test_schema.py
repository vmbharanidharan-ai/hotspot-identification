"""Tests for canonical schema contracts."""

import pytest

pytest.importorskip("pydantic")

from pmhc_hotspot.schema.conditioning import ControlGroup, DesignConditioning, HotspotEntry, PatchEntry
from pmhc_hotspot.schema.design_eval import DesignEvalReport
from pmhc_hotspot.schema.examples import ComplexExample, ExampleProvenance, ExampleSplit


def test_complex_example_roundtrip():
    ex = ComplexExample(
        example_id="1BD2_test",
        allele="HLA-A*02:01",
        peptide_chain="C",
        hla_chains=["A"],
        tcr_chains=["D", "E"],
        peptide_sequence="GILGFVFTL",
        peptide_length=9,
        structure_path="data/pdb/1BD2.pdb",
        split=ExampleSplit.holdout,
        provenance=ExampleProvenance(
            pdb_id="1BD2",
            structure_path="data/pdb/1BD2.pdb",
        ),
    )
    data = ex.model_dump()
    assert ComplexExample.model_validate(data).example_id == "1BD2_test"


def test_design_conditioning_yaml_contract():
    dc = DesignConditioning(
        target_id="1BD2_HLA-A02-01",
        control_group=ControlGroup.predicted,
        peptide={"chain": "C", "sequence": "GILGFVFTL"},
        hotspots=[
            HotspotEntry(residue=4, confidence=0.93, patch_id="A"),
            HotspotEntry(residue=5, confidence=0.88, patch_id="A"),
        ],
        patches=[
            PatchEntry(id="A", center=4, radius=6.0, normal=[0.1, 0.8, -0.6], members=[4, 5, 7]),
        ],
        rfdiffusion={"hotspot_res": "C4,C5,C7", "num_designs": 100, "seed": 42},
    )
    assert dc.control_group == ControlGroup.predicted
    assert len(dc.hotspots) == 2


def test_design_eval_report():
    report = DesignEvalReport(
        target_id="1BD2",
        predicted_beats_controls=[ControlGroup.random],
        gatekeeper_verdict="APPROVE_PROMOTE",
    )
    assert report.gatekeeper_verdict == "APPROVE_PROMOTE"
