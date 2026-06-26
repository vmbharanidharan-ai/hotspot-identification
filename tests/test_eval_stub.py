"""Tests for M6 design eval stub and gatekeeper."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

pytest.importorskip("pydantic")

from pmhc_hotspot.design import DesignExportConfig, export_design_inputs
from pmhc_hotspot.eval import EvalConfig, run_design_eval, run_gatekeeper
from pmhc_hotspot.preprocess import build_example_from_entry
from pmhc_hotspot.benchmark.manifest import BenchmarkEntry
from pmhc_hotspot.schema.examples import ExampleSplit


@pytest.fixture
def pipeline_artifacts(tmp_path: Path) -> Path:
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
    example_path = holdout / f"{example.example_id}.json"
    example_path.write_text(json.dumps(example.model_dump(mode="json"), indent=2))

    design_cfg = DesignExportConfig(
        output_dir=tmp_path / "design_inputs",
        examples_glob=str(holdout / "*.json"),
        scoring_mode="deterministic",
        hotspot_count=3,
    )
    export_design_inputs(design_cfg, repo_root=tmp_path)
    return tmp_path


def test_stub_eval_and_gatekeeper(pipeline_artifacts: Path):
    eval_cfg = EvalConfig(
        seed=42,
        inputs_dir=pipeline_artifacts / "design_inputs",
        metrics_dir=pipeline_artifacts / "metrics",
        stub_mode=True,
    )
    report = run_design_eval(eval_cfg, repo_root=pipeline_artifacts)
    assert report.targets == ["MINI_HLA-A0201"]

    ranking_path = pipeline_artifacts / "metrics" / "MINI_HLA-A0201" / "ranking_report.json"
    assert ranking_path.exists()
    payload = json.loads(ranking_path.read_text())
    assert payload["predicted_beats_controls"]

    decisions = run_gatekeeper(eval_cfg, repo_root=pipeline_artifacts)
    assert decisions[0].verdict == "APPROVE_PROMOTE"

    predicted = yaml.safe_load(
        (pipeline_artifacts / "design_inputs" / "MINI_HLA-A0201" / "predicted.yaml").read_text()
    )
    assert predicted["control_group"] == "predicted"
