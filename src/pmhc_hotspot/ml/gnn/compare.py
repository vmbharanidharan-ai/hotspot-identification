"""Compare XGBoost baseline vs peptide GNN on the same CV splits (M4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd

from pmhc_hotspot.benchmark.stcrdab import default_eval_pdb_ids
from pmhc_hotspot.ml.gnn.config import BaselineCompareConfig
from pmhc_hotspot.ml.gnn.train import train_gnn_cv_from_config
from pmhc_hotspot.ml.train import train_cv


def build_training_frame_for_compare(
    config: BaselineCompareConfig,
    *,
    repo_root: Path | None = None,
) -> pd.DataFrame:
    from pmhc_hotspot.api import HotspotPredictor

    root = repo_root or Path.cwd()
    manifest = config.training_manifest or config.holdout_manifest
    manifest_path = manifest if manifest.is_absolute() else root / manifest

    predictor = HotspotPredictor()
    df = predictor.build_ml_training_frame(
        str(manifest_path),
        download=config.download,
        contact_mode=config.contact_mode,
        cache_dir=str(config.cache_dir if config.cache_dir.is_absolute() else root / config.cache_dir),
    )
    if df.empty:
        return df

    if config.exclude_holdout_from_training:
        holdout = {p.upper() for p in default_eval_pdb_ids()}
        df = df[~df["pdb_id"].astype(str).str.upper().isin(holdout)].copy()
    return df


def compare_xgboost_gnn(
    df: pd.DataFrame,
    config: BaselineCompareConfig,
) -> dict:
    if df.empty:
        raise ValueError("Empty training frame")
    if df["label"].nunique() < 2:
        raise ValueError("Need both positive and negative residue labels")

    xgb_report = train_cv(
        df,
        model_type=config.xgboost_model_type,
        n_splits=config.n_splits,
        random_state=config.seed,
    )
    gnn_report = train_gnn_cv_from_config(
        df,
        {
            "n_splits": config.n_splits,
            "random_state": config.seed,
            **config.gnn_dict(),
        },
    )

    xgb_auc = xgb_report["overall"]["roc_auc"]
    gnn_auc = gnn_report["overall"]["roc_auc"]
    delta = gnn_auc - xgb_auc if xgb_auc == xgb_auc and gnn_auc == gnn_auc else float("nan")

    return {
        "n_rows": len(df),
        "n_positive": int(df["label"].sum()),
        "n_structures": int(df["pdb_id"].nunique()) if "pdb_id" in df.columns else None,
        "xgboost": xgb_report,
        "gnn": gnn_report,
        "comparison": {
            "xgboost_roc_auc": xgb_auc,
            "gnn_roc_auc": gnn_auc,
            "gnn_minus_xgboost_roc_auc": delta,
            "gnn_beats_xgboost": bool(delta == delta and delta > 0),
            "primary_metric": "roc_auc",
        },
    }


def run_baseline_compare(
    config: BaselineCompareConfig,
    df: Optional[pd.DataFrame] = None,
    *,
    repo_root: Path | None = None,
) -> dict:
    root = repo_root or Path.cwd()
    frame = df if df is not None else build_training_frame_for_compare(config, repo_root=root)
    report = compare_xgboost_gnn(frame, config)
    out_path = config.output_report if config.output_report.is_absolute() else root / config.output_report
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2))
    report["output_report"] = str(out_path)
    return report
