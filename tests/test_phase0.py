"""Tests for Phase 0 foundation modules."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from pmhc_hotspot.automation.label_generator import ContactLabelGenerator
from pmhc_hotspot.automation.pdb_crawler import PDBStructureAnalyzer
from pmhc_hotspot.design.control_strategies import get_strategy
from pmhc_hotspot.hotspot_export import export_hotspot_yaml, import_hotspot_yaml
from pmhc_hotspot.uncertainty import ConfidenceEstimator


@pytest.fixture
def mini_pdb(tmp_path: Path) -> Path:
    repo = Path(__file__).resolve().parents[1]
    dest = tmp_path / "MINI.pdb"
    shutil.copy(repo / "examples" / "minimal_pmhc.pdb", dest)
    return dest


def test_structure_analyzer_minimal(mini_pdb: Path):
    inference = PDBStructureAnalyzer().analyze(mini_pdb)
    assert inference.peptide_chain == "P"
    assert inference.mhc_chain == "H"


def test_label_generator_minimal(mini_pdb: Path):
    gen = ContactLabelGenerator(contact_mode="standard")
    payload = gen.label_structure(mini_pdb, peptide_chain="P", hla_chain="H", tcr_chains=[])
    assert "P1" in payload["residues"]
    assert "contact_entropy" in payload["residues"]["P1"]


def test_hotspot_yaml_roundtrip(tmp_path: Path, mini_pdb: Path):
    from pmhc_hotspot import HotspotPredictor

    result = HotspotPredictor(allele="HLA-A*02:01", peptide_chain="P", hla_chain="H").predict(mini_pdb)
    out = tmp_path / "hotspot.yaml"
    export_hotspot_yaml(
        result,
        pdb_id="MINI",
        peptide_seq=result.peptide_sequence,
        allele=result.allele,
        tcr_chains=[],
        output_file=out,
    )
    data = import_hotspot_yaml(out)
    assert data["metadata"]["pdb_id"] == "MINI"
    assert data["hotspots"]


def test_confidence_estimator():
    est = ConfidenceEstimator()
    assert est.calibrate_score(0.7) > 0.0


def test_control_strategies(mini_pdb: Path):
    strat = get_strategy("random")
    picks = strat.select_residues(mini_pdb, "P", n_select=3, seed=1)
    assert len(picks) == 3
