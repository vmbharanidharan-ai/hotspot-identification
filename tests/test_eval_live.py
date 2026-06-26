"""Tests for M6 live candidates.csv evaluation."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import pytest

pytest.importorskip("pydantic")

from pmhc_hotspot.design import DesignExportConfig, export_design_inputs
from pmhc_hotspot.eval import EvalConfig, run_design_eval
from pmhc_hotspot.preprocess import build_example_from_entry
from pmhc_hotspot.benchmark.manifest import BenchmarkEntry
from pmhc_hotspot.schema.examples import ExampleSplit


@pytest.fixture
def live_eval_tree(tmp_path: Path) -> Path:
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

    design_cfg = DesignExportConfig(
        output_dir=tmp_path / "design_inputs",
        examples_glob=str(holdout / "*.json"),
        scoring_mode="deterministic",
        hotspot_count=3,
        write_job_manifests=False,
    )
    export_design_inputs(design_cfg, repo_root=tmp_path)

    outputs = tmp_path / "design_outputs" / example.example_id
    for group, mean_ipae in [
        ("random", 14.0),
        ("exposed_only", 12.5),
        ("central_only", 11.8),
        ("predicted", 8.5),
    ]:
        group_dir = outputs / group
        group_dir.mkdir(parents=True)
        csv_path = group_dir / "candidates.csv"
        with csv_path.open("w", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=["candidate_id", "seed", "af2_ipae", "hotspot_contact_fraction"],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "candidate_id": f"{example.example_id}_{group}_001",
                    "seed": "42",
                    "af2_ipae": str(mean_ipae),
                    "hotspot_contact_fraction": "0.5",
                }
            )
    return tmp_path


def test_live_candidates_csv_eval(live_eval_tree: Path):
    cfg = EvalConfig(
        inputs_dir=live_eval_tree / "design_inputs",
        outputs_dir=live_eval_tree / "design_outputs",
        metrics_dir=live_eval_tree / "metrics",
        stub_mode=False,
    )
    report = run_design_eval(cfg, repo_root=live_eval_tree)
    assert report.targets == ["MINI_HLA-A0201"]

    ranking = json.loads(
        (live_eval_tree / "metrics" / "MINI_HLA-A0201" / "ranking_report.json").read_text()
    )
    assert ranking["notes"] == "live_outputs"
    assert ranking["predicted_beats_controls"]
    predicted = next(
        c for c in ranking["comparisons"] if c["control_group"] == "predicted"
    )
    assert predicted["mean_primary"] == pytest.approx(8.5)
