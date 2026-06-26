"""Tests for M5 design-conditioning export."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

pytest.importorskip("pydantic")

from pmhc_hotspot.design import DesignExportConfig, export_design_inputs
from pmhc_hotspot.preprocess import build_example_from_entry
from pmhc_hotspot.benchmark.manifest import BenchmarkEntry
from pmhc_hotspot.schema.conditioning import ControlGroup
from pmhc_hotspot.schema.examples import ExampleSplit


@pytest.fixture
def minimal_example(tmp_path: Path) -> Path:
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
    holdout_dir = tmp_path / "examples" / "holdout"
    holdout_dir.mkdir(parents=True)
    out = holdout_dir / f"{example.example_id}.json"
    out.write_text(json.dumps(example.model_dump(mode="json"), indent=2))
    return tmp_path


def test_export_all_control_groups(minimal_example: Path):
    output_dir = minimal_example / "design_inputs"
    cfg = DesignExportConfig(
        seed=42,
        scoring_mode="deterministic",
        output_dir=output_dir,
        examples_glob=str(minimal_example / "examples" / "holdout" / "*.json"),
        hotspot_count=3,
    )
    report = export_design_inputs(cfg, repo_root=minimal_example)
    assert len(report.exported) == 4
    target_dir = output_dir / "MINI_HLA-A0201"
    for group in ControlGroup:
        path = target_dir / f"{group.value}.yaml"
        assert path.exists(), group.value
        data = yaml.safe_load(path.read_text())
        assert data["control_group"] == group.value
        assert len(data["hotspots"]) >= 1
        assert data["rfdiffusion"]["hotspot_res"]


def test_random_control_is_seed_stable(minimal_example: Path):
    output_dir = minimal_example / "design_inputs"
    cfg = DesignExportConfig(
        seed=99,
        scoring_mode="deterministic",
        output_dir=output_dir,
        examples_glob=str(minimal_example / "examples" / "holdout" / "*.json"),
        hotspot_count=3,
    )
    export_design_inputs(cfg, repo_root=minimal_example)
    first = yaml.safe_load(
        (output_dir / "MINI_HLA-A0201" / "random.yaml").read_text()
    )

    output_dir2 = minimal_example / "design_inputs2"
    cfg.output_dir = output_dir2
    export_design_inputs(cfg, repo_root=minimal_example)
    second = yaml.safe_load(
        (output_dir2 / "MINI_HLA-A0201" / "random.yaml").read_text()
    )
    assert first["rfdiffusion"]["hotspot_res"] == second["rfdiffusion"]["hotspot_res"]
