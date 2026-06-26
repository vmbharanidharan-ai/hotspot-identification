#!/usr/bin/env python3
"""Copy promoted champion model metadata after gates pass."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone

from pmhc_hotspot.automation.paths import (
    BENCHMARK_REPORT_PATH,
    CHAMPION_META_PATH,
    CHAMPION_MODEL_PATH,
    METRICS_GATE_PATH,
    MODELS_DIR,
    TRAINING_REPORT_PATH,
    ensure_artifact_dirs,
)
from pmhc_hotspot.ml.persistence import default_model_path, save_staged_bundle
from pmhc_hotspot.ml.persistence import load_staged_bundle


def main() -> int:
    ensure_artifact_dirs()
    if not METRICS_GATE_PATH.exists():
        print(f"Missing metrics gate report: {METRICS_GATE_PATH}", file=sys.stderr)
        return 1

    with METRICS_GATE_PATH.open() as fh:
        gate = json.load(fh)
    if not gate.get("promote_model"):
        print("Promotion rejected by metrics/biology gates.", file=sys.stderr)
        return 1

    candidate_path = MODELS_DIR / "staged_xgb.joblib"
    if not candidate_path.exists():
        print(f"Missing candidate model: {candidate_path}", file=sys.stderr)
        return 1

    bundle = load_staged_bundle(candidate_path)
    shutil.copy2(candidate_path, CHAMPION_MODEL_PATH)
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

    print(f"Promoted champion: {CHAMPION_MODEL_PATH}")
    print(f"Updated packaged default: {default_model_path()}")
    print(f"Wrote {CHAMPION_META_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
