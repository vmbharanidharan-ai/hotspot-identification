#!/usr/bin/env python3
"""
Binder-conditioning pipeline orchestrator (Python).

Loads configs, dispatches phases, writes run manifest.
Cursor agents implement individual phases; this script is the stable CLI entry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = REPO_ROOT / "artifacts"


def _load_config(name: str) -> dict:
    path = REPO_ROOT / "configs" / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Missing config: {path}")
    with path.open() as fh:
        return yaml.safe_load(fh) or {}


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def write_run_manifest(phase: str, configs: dict[str, dict]) -> Path:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    config_blob = json.dumps(configs, sort_keys=True)
    manifest = {
        "phase": phase,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "commit": _git_commit(),
        "config_hash": hashlib.sha256(config_blob.encode()).hexdigest()[:16],
        "configs": {k: str(REPO_ROOT / "configs" / f"{k}.yaml") for k in configs},
    }
    path = ARTIFACTS / "reports" / "pipeline_run_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2))
    return path


def run_ingest() -> int:
    """Phase 1: build ComplexExample JSON from configs/dataset.yaml."""
    from pmhc_hotspot.preprocess import DatasetBuildConfig, build_dataset

    config_path = REPO_ROOT / "configs" / "dataset.yaml"
    cfg = DatasetBuildConfig.from_yaml(config_path)
    report = build_dataset(cfg, repo_root=REPO_ROOT)
    print(f"Built {len(report.built)} examples → {cfg.processed_dir}/examples/")
    print(f"Skipped {len(report.skipped)} structures")
    print(f"Manifest: {cfg.output_manifest}")
    return 0 if report.built or not report.skipped else 1


def run_design_export() -> int:
    """M5: export four control-group conditioning YAML per target."""
    from pmhc_hotspot.design import DesignExportConfig, export_design_inputs

    config_path = REPO_ROOT / "configs" / "design.yaml"
    cfg = DesignExportConfig.from_yaml(config_path)
    report = export_design_inputs(cfg, repo_root=REPO_ROOT)
    print(f"Exported {len(report.exported)} conditioning files → {cfg.output_dir}/")
    print(f"Skipped {len(report.skipped)} targets")
    if report.skipped:
        for row in report.skipped[:5]:
            print(f"  skip {row.get('example_id')}: {row.get('error')}")
    return 0 if report.exported or not report.skipped else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "phase",
        choices=["ingest", "features", "design-export", "design-eval", "all"],
        nargs="?",
        default="all",
    )
    args = parser.parse_args()

    configs = {}
    if args.phase in {"ingest", "all"}:
        configs["dataset"] = _load_config("dataset")
    if args.phase in {"design-export", "all"}:
        configs["design"] = _load_config("design")
    if args.phase in {"design-eval", "all"}:
        configs["eval"] = _load_config("eval")

    manifest_path = write_run_manifest(args.phase, configs)
    print(f"Run manifest: {manifest_path}")
    print(f"Phase: {args.phase}")

    if args.phase == "ingest":
        return run_ingest()
    if args.phase == "design-export":
        return run_design_export()
    if args.phase == "all":
        code = run_ingest()
        if code != 0:
            return code
        return run_design_export()

    print("Next: invoke Cursor orchestrator agent or SDK launcher.")
    print("  IDE: ask the orchestrator subagent to run the next phase")
    print("  SDK: python scripts/launch_design_cycle.py <phase>")
    print("See docs/DESIGN_PIPELINE_RUNBOOK.md and pmhc-hotspot-dev-plan.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
