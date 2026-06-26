"""Shared artifact and data paths for training automation."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS_DIR = Path(os.environ.get("PMHC_ARTIFACTS_DIR", REPO_ROOT / "artifacts"))
MODELS_DIR = ARTIFACTS_DIR / "models"
REPORTS_DIR = ARTIFACTS_DIR / "reports"
BASELINE_METRICS_PATH = Path(
    os.environ.get("PMHC_BASELINE_METRICS", REPO_ROOT / "baseline_metrics.json")
)
CHAMPION_MODEL_PATH = MODELS_DIR / "staged_xgb.joblib"
CHAMPION_META_PATH = MODELS_DIR / "champion_metrics.json"
TRAINING_REPORT_PATH = REPORTS_DIR / "training_report.json"
BENCHMARK_REPORT_PATH = REPORTS_DIR / "benchmark_report.json"
BIOLOGY_REPORT_PATH = REPORTS_DIR / "biology_gate.json"
METRICS_GATE_PATH = REPORTS_DIR / "metrics_gate.json"
PATCH_BRIEF_PATH = REPORTS_DIR / "patch_brief.json"

DEFAULT_IEDB_PATH = Path(os.environ.get("PMHC_IEDB_PATH", REPO_ROOT / "data" / "iedb_mhc_ligand.csv"))
DEFAULT_PDB_CACHE = Path(os.environ.get("PMHC_PDB_CACHE", REPO_ROOT / "data" / "pdb"))
SMOKE_IEDB_PATH = REPO_ROOT / "tests" / "data" / "sample_iedb_native.csv"
SMOKE_MANIFEST_PATH = REPO_ROOT / "tests" / "data" / "benchmark_mini.yaml"


def ensure_artifact_dirs() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
