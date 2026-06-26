#!/usr/bin/env python3
"""Copy promoted champion model metadata after gates pass."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from pmhc_hotspot.automation.paths import (
    BENCHMARK_REPORT_PATH,
    CHAMPION_META_PATH,
    CHAMPION_MODEL_PATH,
    METRICS_GATE_PATH,
    MODELS_DIR,
    REPO_ROOT,
    TRAINING_REPORT_PATH,
    ensure_artifact_dirs,
)
from pmhc_hotspot.ml.persistence import default_model_path, load_staged_bundle, save_staged_bundle


def _resolve_candidate(path: Path | None) -> Path:
    if path is not None:
        return path
    env = os.environ.get("PMHC_CANDIDATE_MODEL")
    if env:
        return Path(env)
    for candidate in (
        MODELS_DIR / "staged_xgb.joblib",
        REPO_ROOT / "data" / "models" / "staged_xgb_training.joblib",
        REPO_ROOT / "data" / "models" / "staged_xgb.joblib",
    ):
        if candidate.exists():
            return candidate
    return MODELS_DIR / "staged_xgb.joblib"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate",
        type=Path,
        default=None,
        help="Model bundle to promote (default: artifacts/models/staged_xgb.joblib)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    ensure_artifact_dirs()
    if not METRICS_GATE_PATH.exists():
        print(f"Missing metrics gate report: {METRICS_GATE_PATH}", file=sys.stderr)
        return 1

    with METRICS_GATE_PATH.open() as fh:
        gate = json.load(fh)
    if not gate.get("promote_model"):
        print("Promotion rejected by metrics/biology gates.", file=sys.stderr)
        return 1

    candidate_path = _resolve_candidate(args.candidate).resolve()
    if not candidate_path.exists():
        print(f"Missing candidate model: {candidate_path}", file=sys.stderr)
        return 1

    bundle = load_staged_bundle(candidate_path)
    champion_path = CHAMPION_MODEL_PATH.resolve()
    if candidate_path != champion_path:
        shutil.copy2(candidate_path, champion_path)
    save_staged_bundle(default_model_path(), bundle)

    with TRAINING_REPORT_PATH.open() as fh:
        training_report = json.load(fh)
    with BENCHMARK_REPORT_PATH.open() as fh:
        benchmark_report = json.load(fh)

    champion_meta = {
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "training": {
            "pretrain_roc_auc": (training_report.get("pretrain_cv") or {}).get("roc_auc"),
            "statistical_roc_auc": (training_report.get("statistical_cv") or {})
            .get("overall", {})
            .get("roc_auc"),
            "finetune_roc_auc": (training_report.get("finetune_cv") or {})
            .get("overall", {})
            .get("roc_auc"),
        },
        "benchmark": {
            "scoring_mode": benchmark_report.get("scoring_mode"),
            "mean_recall_at_5": (benchmark_report.get("summary") or {}).get("mean_recall_at_5"),
            "mean_buried_anchor_avoidance_at_5": (benchmark_report.get("summary") or {}).get(
                "mean_buried_anchor_avoidance_at_5"
            ),
        },
        "model_paths": {
            "champion": str(CHAMPION_MODEL_PATH),
            "packaged_default": str(default_model_path()),
        },
    }
    with CHAMPION_META_PATH.open("w") as fh:
        json.dump(champion_meta, fh, indent=2)

    print(f"Promoted champion: {champion_path}")
    if candidate_path == champion_path:
        print(f"Candidate already at champion path: {candidate_path}")
    print(f"Updated packaged default: {default_model_path()}")
    print(f"Wrote {CHAMPION_META_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
