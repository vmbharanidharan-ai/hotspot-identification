"""Tests for M3 docking geometry priors."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

pytest.importorskip("pydantic")

from pmhc_hotspot.benchmark.manifest import BenchmarkEntry
from pmhc_hotspot.docking import DockingPriorConfig, geometry_consensus_priors
from pmhc_hotspot.features.config import FeatureComputeConfig
from pmhc_hotspot.preprocess import build_example_from_entry, enrich_examples
from pmhc_hotspot.schema.examples import ExampleSplit
from pmhc_hotspot.api import HotspotPredictor


@pytest.fixture
def minimal_structure(tmp_path: Path) -> Path:
    repo = Path(__file__).resolve().parents[1]
    dest = tmp_path / "MINI.pdb"
    shutil.copy(repo / "examples" / "minimal_pmhc.pdb", dest)
    return dest


def test_geometry_consensus_priors_bounded(minimal_structure: Path):
    predictor = HotspotPredictor(
        allele="HLA-A*02:01",
        peptide_chain="P",
        hla_chain="H",
        scoring_mode="deterministic",
    )
    result = predictor.predict(minimal_structure, select_hotspots=False)
    cfg = DockingPriorConfig()
    priors = geometry_consensus_priors(result.residue_scores, cfg.weights)
    assert len(priors) == len(result.residue_scores)
    assert all(0.0 <= p <= 1.0 for p in priors)


def test_docking_prior_on_example_enrich(tmp_path: Path, minimal_structure: Path):
    entry = BenchmarkEntry(
        pdb_id="MINI",
        allele="HLA-A*02:01",
        peptide_chain="P",
        hla_chain="H",
        tcr_chains=(),
        pdb_path=str(minimal_structure),
    )
    example = build_example_from_entry(
        entry,
        structure_path=minimal_structure,
        split=ExampleSplit.holdout,
    )
    out = tmp_path / "example.json"
    out.write_text(json.dumps(example.model_dump(mode="json"), indent=2))

    dock_cfg = tmp_path / "docking.yaml"
    dock_cfg.write_text(
        "enabled: true\nmethod: geometry_consensus\nweights:\n  relative_sasa: 0.5\n  protrusion: 0.5\n"
    )

    cfg = FeatureComputeConfig(
        examples_glob=str(out),
        in_place=True,
        docking_prior=True,
        docking_config=dock_cfg,
    )
    enrich_examples(cfg, paths=[out], repo_root=tmp_path)
    payload = json.loads(out.read_text())
    priors = [f["docking_contact_prior"] for f in payload["residue_features"]]
    assert any(p is not None and p > 0 for p in priors)
