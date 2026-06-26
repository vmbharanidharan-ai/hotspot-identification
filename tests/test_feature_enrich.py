"""Tests for feature enrichment on ComplexExample."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

pytest.importorskip("pydantic")

from pmhc_hotspot.benchmark.manifest import BenchmarkEntry
from pmhc_hotspot.features.config import FeatureComputeConfig
from pmhc_hotspot.preprocess import build_example_from_entry, enrich_examples
from pmhc_hotspot.schema.examples import ExampleSplit


@pytest.fixture
def example_json(tmp_path: Path) -> Path:
    repo = Path(__file__).resolve().parents[1]
    structure = tmp_path / "MINI.pdb"
    shutil.copy(repo / "examples" / "minimal_pmhc.pdb", structure)
    entry = BenchmarkEntry(
        pdb_id="MINI",
        allele="HLA-A*02:01",
        peptide_chain="P",
        hla_chain="H",
        tcr_chains=(),
        pdb_path=str(structure),
    )
    example = build_example_from_entry(
        entry,
        structure_path=structure,
        split=ExampleSplit.holdout,
    )
    out = tmp_path / "example.json"
    out.write_text(json.dumps(example.model_dump(mode="json"), indent=2))
    return out


def test_enrich_example_adds_residue_features(example_json: Path):
    cfg = FeatureComputeConfig(
        examples_glob=str(example_json),
        in_place=True,
        scoring_mode="deterministic",
    )
    report = enrich_examples(cfg, paths=[example_json], repo_root=example_json.parent)
    assert report.enriched == ["MINI_HLA-A0201"]

    payload = json.loads(example_json.read_text())
    assert len(payload["residue_features"]) == 9
    assert payload["residue_features"][0]["position"] == "P1"
    assert payload["residue_features"][0]["relative_sasa"] >= 0.0
