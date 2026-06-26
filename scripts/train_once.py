#!/usr/bin/env python3
"""Run one staged training cycle and write CI artifacts."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from pmhc_hotspot.api import HotspotPredictor
from pmhc_hotspot.automation.paths import (
    CHAMPION_MODEL_PATH,
    DEFAULT_IEDB_PATH,
    DEFAULT_PDB_CACHE,
    MODELS_DIR,
    REPORTS_DIR,
    SMOKE_MANIFEST_PATH,
    TRAINING_REPORT_PATH,
    ensure_artifact_dirs,
)
from pmhc_hotspot.data.public_datasets import load_iedb_csv
from pmhc_hotspot.ml.persistence import save_staged_bundle
from pmhc_hotspot.ml.staged import run_staged_training


def _smoke_mode() -> bool:
    return os.environ.get("PMHC_ALLOW_SMOKE_TRAIN", "").lower() in {"1", "true", "yes"}


def main() -> int:
    ensure_artifact_dirs()

    if not DEFAULT_IEDB_PATH.exists():
        print("IEDB missing; run scripts/fetch_iedb.py first.", file=sys.stderr)
        return 1

    smoke = _smoke_mode()
    manifest_path = str(SMOKE_MANIFEST_PATH) if smoke else None
    download = not smoke
    no_pretrain = smoke

    try:
        public_df = None if no_pretrain else load_iedb_csv(DEFAULT_IEDB_PATH)
        if no_pretrain:
            import pandas as pd

            public_df = pd.DataFrame()

        structural_df = HotspotPredictor().build_ml_training_frame(
            manifest_path,
            download=download,
            contact_mode=os.environ.get("PMHC_CONTACT_MODE", "standard"),
            cache_dir=str(DEFAULT_PDB_CACHE),
        )
        if structural_df.empty:
            raise RuntimeError("No structural training rows produced")

        report = run_staged_training(
            public_df,
            structural_df,
            model_type=os.environ.get("PMHC_MODEL_TYPE", "xgboost"),
            n_splits=int(os.environ.get("PMHC_CV_SPLITS", "5")),
            contact_mode=os.environ.get("PMHC_CONTACT_MODE", "standard"),
            use_pretrain=not no_pretrain,
            calibrate=os.environ.get("PMHC_NO_CALIBRATE", "").lower() not in {"1", "true", "yes"},
        )
    except Exception as exc:
        failure = {"status": "failed", "error": str(exc), "smoke_mode": smoke}
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        with (REPORTS_DIR / "training_failure.json").open("w") as fh:
            json.dump(failure, fh, indent=2)
        print(f"Training failed: {exc}", file=sys.stderr)
        return 1

    model_path = MODELS_DIR / "staged_xgb.joblib"
    save_staged_bundle(model_path, report["model_bundle"])

    serializable = {
        "status": "ok",
        "smoke_mode": smoke,
        "pretrain_cv": report["pretrain_cv"],
        "statistical_cv": {
            k: v for k, v in report["statistical_cv"].items() if k != "oof_predictions"
        },
        "finetune_cv": report["finetune_cv"],
        "hybrid_alpha": report["hybrid_alpha"],
        "n_public_rows": report["n_public_rows"],
        "n_structural_rows": report["n_structural_rows"],
        "contact_mode": report["contact_mode"],
        "use_pretrain": report["use_pretrain"],
        "calibrated": report["calibrated"],
        "model_path": str(model_path),
    }
    with TRAINING_REPORT_PATH.open("w") as fh:
        json.dump(serializable, fh, indent=2, default=str)

    if CHAMPION_MODEL_PATH.exists():
        serializable["previous_champion"] = str(CHAMPION_MODEL_PATH)

    print(f"Saved model: {model_path}")
    if report["pretrain_cv"]:
        print(f"Pretrain ROC-AUC: {report['pretrain_cv']['roc_auc']:.3f}")
    print(f"Statistical ROC-AUC: {report['statistical_cv']['overall']['roc_auc']:.3f}")
    print(f"Finetune ROC-AUC: {report['finetune_cv']['overall']['roc_auc']:.3f}")
    print(f"Hybrid alpha: {report['hybrid_alpha']:.3f}")
    print(f"Wrote {TRAINING_REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
