"""Tests for RFdiffusion job manifest export."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

pytest.importorskip("pydantic")

from pmhc_hotspot.design import DesignExportConfig, export_design_inputs
from pmhc_hotspot.preprocess import build_example_from_entry
from pmhc_hotspot.benchmark.manifest import BenchmarkEntry
from pmhc_hotspot.schema.examples import ExampleSplit


@pytest.fixture
def design_inputs(tmp_path: Path) -> Path:
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
    holdout = tmp_path / "examples" / "holdout"
    holdout.mkdir(parents=True)
    (holdout / f"{example.example_id}.json").write_text(
        json.dumps(example.model_dump(mode="json"), indent=2)
    )

    cfg = DesignExportConfig(
        output_dir=tmp_path / "design_inputs",
        examples_glob=str(holdout / "*.json"),
        scoring_mode="deterministic",
        hotspot_count=3,
        write_job_manifests=True,
    )
    export_design_inputs(cfg, repo_root=tmp_path)
    return tmp_path / "design_inputs"


def test_rfdiffusion_job_manifest(design_inputs: Path):
    jobs_path = design_inputs / "MINI_HLA-A0201" / "rfdiffusion_jobs.json"
    assert jobs_path.exists()
    payload = json.loads(jobs_path.read_text())
    assert len(payload["jobs"]) == 4
    assert payload["jobs"][0]["backend"] == "rfdiffusion"
    assert payload["jobs"][0]["status"] == "pending"
