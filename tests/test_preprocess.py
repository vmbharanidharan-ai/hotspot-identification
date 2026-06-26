"""Tests for Phase 1 ingest (ComplexExample builder)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

pytest.importorskip("pydantic")

from pmhc_hotspot.benchmark.manifest import BenchmarkEntry
from pmhc_hotspot.preprocess import DatasetBuildConfig, build_dataset, build_example_from_entry
from pmhc_hotspot.schema.examples import ExampleSplit


@pytest.fixture
def minimal_structure(tmp_path: Path) -> Path:
    repo = Path(__file__).resolve().parents[1]
    dest = tmp_path / "MINI.pdb"
    shutil.copy(repo / "examples" / "minimal_pmhc.pdb", dest)
    return dest


@pytest.fixture
def mini_manifest(tmp_path: Path, minimal_structure: Path) -> Path:
    path = tmp_path / "mini.yaml"
    path.write_text(
        f"""structures:
  - pdb_id: MINI
    allele: HLA-A*02:01
    peptide_chain: P
    hla_chain: H
    tcr_chains: []
    pdb_path: {minimal_structure}
"""
    )
    return path


def test_build_example_from_minimal_pmhc(minimal_structure: Path):
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
        split=ExampleSplit.train,
        contact_mode="standard",
    )
    assert example.peptide_length == 9
    assert example.peptide_chain == "P"
    assert "H" in example.hla_chains
    assert example.labels is not None
    assert example.labels.tcr_contact_positions == []


def test_build_dataset_offline(tmp_path: Path, mini_manifest: Path, minimal_structure: Path):
    processed = tmp_path / "processed"
    cfg = DatasetBuildConfig(
        processed_dir=processed,
        cache_dir=tmp_path / "pdb",
        sources=["pdb_manifest"],
        holdout_manifest=mini_manifest,
        download=False,
        skip_missing=True,
        output_manifest=processed / "dataset_manifest.json",
    )
    report = build_dataset(cfg)
    assert len(report.built) == 1
    example_path = processed / "examples" / "train" / "MINI_HLA-A0201.json"
    assert example_path.exists()
    payload = json.loads(example_path.read_text())
    assert payload["peptide_sequence"] == "GALVYRFWL"
    assert (processed / "ingest_report.json").exists()
