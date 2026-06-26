#!/usr/bin/env python3
"""Benchmark the latest trained model and write CI artifacts."""

from __future__ import annotations

import json
import os
import sys

from pmhc_hotspot.api import HotspotPredictor
from pmhc_hotspot.automation.paths import (
    BENCHMARK_REPORT_PATH,
    CHAMPION_MODEL_PATH,
    DEFAULT_PDB_CACHE,
    MODELS_DIR,
    REPORTS_DIR,
    SMOKE_MANIFEST_PATH,
    TRAINING_REPORT_PATH,
    ensure_artifact_dirs,
)
from pmhc_hotspot.ml.persistence import resolve_model_bundle_path


def main() -> int:
    ensure_artifact_dirs()

    model_path = resolve_model_bundle_path(MODELS_DIR / "staged_xgb.joblib", allow_missing=True)
    if model_path is None:
        print("No trained model found in artifacts/models/", file=sys.stderr)
        return 1

    smoke = os.environ.get("PMHC_ALLOW_SMOKE_TRAIN", "").lower() in {"1", "true", "yes"}
    manifest_path = str(SMOKE_MANIFEST_PATH) if smoke else None
    scoring_mode = os.environ.get("PMHC_BENCHMARK_SCORING_MODE", "hybrid")
    download = not smoke

    predictor = HotspotPredictor(ml_bundle=str(model_path), scoring_mode=scoring_mode)
    report = predictor.benchmark(
        manifest_path,
        download=download,
        cache_dir=str(DEFAULT_PDB_CACHE),
        contact_mode=os.environ.get("PMHC_CONTACT_MODE", "standard"),
        scoring_mode=scoring_mode,
        ml_bundle=str(model_path),
    )

    # deterministic baseline on the same manifest for comparison
    det_report = predictor.benchmark(
        manifest_path,
        download=False,
        cache_dir=str(DEFAULT_PDB_CACHE),
        contact_mode=os.environ.get("PMHC_CONTACT_MODE", "standard"),
        scoring_mode="deterministic",
        ml_bundle=None,
    )

    payload = {
        "status": "ok",
        "smoke_mode": smoke,
        "model_path": str(model_path),
        "scoring_mode": scoring_mode,
        "training_report_path": str(TRAINING_REPORT_PATH),
        "summary": report.get("summary", {}),
        "contact_mode": report.get("contact_mode"),
        "results": report.get("results", []),
        "deterministic_summary": det_report.get("summary", {}),
    }
    with BENCHMARK_REPORT_PATH.open("w") as fh:
        json.dump(payload, fh, indent=2, default=str)

    summary = report.get("summary", {})
    print(f"Model: {model_path}")
    print(f"Scoring mode: {scoring_mode}")
    print(f"Structures evaluated: {summary.get('n_structures', 0)}")
    if summary.get("n_structures"):
        print(f"Mean recall@5: {summary.get('mean_recall_at_5', 0):.3f}")
        buried = summary.get("mean_buried_anchor_avoidance_at_5")
        if buried == buried:
            print(f"Mean buried-anchor avoidance@5: {buried:.3f}")
    print(f"Wrote {BENCHMARK_REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
