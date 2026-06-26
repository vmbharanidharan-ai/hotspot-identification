#!/usr/bin/env python3
"""Benchmark the fixed 11-PDB eval manifest (package quality metric)."""

from __future__ import annotations

import argparse
import json
import os
import sys

from pmhc_hotspot.api import HotspotPredictor
from pmhc_hotspot.automation.overnight import save_eval_baseline_if_missing
from pmhc_hotspot.automation.paths import (
    DEFAULT_PDB_CACHE,
    EVAL_BENCHMARK_REPORT_PATH,
    ensure_artifact_dirs,
)
from pmhc_hotspot.ml.persistence import resolve_default_model_bundle, resolve_model_bundle_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scoring-mode",
        default=os.environ.get("PMHC_EVAL_SCORING_MODE", "hybrid"),
        choices=["deterministic", "statistical", "ml", "hybrid"],
    )
    parser.add_argument("--cache-dir", default=str(DEFAULT_PDB_CACHE))
    parser.add_argument("--download", action="store_true", default=True)
    parser.add_argument("--no-download", action="store_false", dest="download")
    parser.add_argument("--save-baseline", action="store_true")
    parser.add_argument("--out", type=str, default=str(EVAL_BENCHMARK_REPORT_PATH))
    args = parser.parse_args()

    ensure_artifact_dirs()
    model_path = None
    scoring_mode = args.scoring_mode
    if scoring_mode != "deterministic":
        try:
            model_path = str(resolve_model_bundle_path(allow_missing=False))
        except FileNotFoundError:
            bundle = resolve_default_model_bundle(allow_missing=True)
            if bundle is None:
                print(
                    "No ML bundle found; falling back to deterministic eval.",
                    file=sys.stderr,
                )
                scoring_mode = "deterministic"
            else:
                model_path = str(resolve_model_bundle_path(allow_missing=True))

    predictor = HotspotPredictor(
        ml_bundle=model_path,
        scoring_mode=scoring_mode,
    )
    report = predictor.benchmark(
        None,
        download=args.download,
        cache_dir=args.cache_dir,
        scoring_mode=scoring_mode,
        ml_bundle=model_path,
    )
    det_report = predictor.benchmark(
        None,
        download=False,
        cache_dir=args.cache_dir,
        scoring_mode="deterministic",
        ml_bundle=None,
    )

    payload = {
        "status": "ok",
        "purpose": "package_eval_fixed_manifest",
        "scoring_mode": scoring_mode,
        "model_path": model_path,
        "summary": report.get("summary", {}),
        "results": report.get("results", []),
        "deterministic_summary": det_report.get("summary", {}),
    }
    out_path = args.out
    with open(out_path, "w") as fh:
        json.dump(payload, fh, indent=2, default=str)

    if args.save_baseline:
        save_eval_baseline_if_missing(payload)

    summary = payload["summary"]
    print(f"Eval manifest structures: {summary.get('n_structures', 0)}")
    print(f"Scoring mode: {scoring_mode}")
    if summary.get("n_structures"):
        print(f"Mean recall@5: {summary.get('mean_recall_at_5', 0):.3f}")
        buried = summary.get("mean_buried_anchor_avoidance_at_5")
        if buried == buried:
            print(f"Mean buried-anchor avoidance@5: {buried:.3f}")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
