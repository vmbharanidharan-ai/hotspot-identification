"""Compare training/benchmark metrics against baseline and champion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open() as fh:
        return json.load(fh)


def load_baseline_metrics(path: Path | None = None) -> dict:
    from pmhc_hotspot.automation.paths import BASELINE_METRICS_PATH

    return load_json(path or BASELINE_METRICS_PATH)


def _get_nested(data: dict, *keys: str, default: float | None = None) -> float | None:
    cur: Any = data
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    if cur is None:
        return default
    return float(cur)


def compare_metrics(
    *,
    training_report: dict | None = None,
    benchmark_report: dict | None = None,
    baseline: dict | None = None,
    champion: dict | None = None,
    min_improvement: float = 0.0,
    auc_tolerance: float = 0.005,
) -> dict:
    """
    Decide whether a candidate run should be promoted.

    Promotion requires (within ``auc_tolerance`` for CV noise):
    - finetune ROC-AUC >= baseline (if present), unless benchmark recall clearly improves
    - hybrid recall@5 >= baseline (if benchmark baseline present)
    - no regression vs champion on either metric (if champion exists)
    """
    baseline = baseline or load_baseline_metrics()
    champion = champion or {}

    candidate_training = training_report or {}
    candidate_benchmark = benchmark_report or {}

    finetune_auc = _get_nested(candidate_training, "finetune_cv", "overall", "roc_auc")
    stat_auc = _get_nested(candidate_training, "statistical_cv", "overall", "roc_auc")
    pretrain_auc = _get_nested(candidate_training, "pretrain_cv", "roc_auc")

    scoring_mode = candidate_benchmark.get("scoring_mode", "hybrid")
    recall_at_5 = _get_nested(candidate_benchmark, "summary", "mean_recall_at_5")
    buried_avoid = _get_nested(candidate_benchmark, "summary", "mean_buried_anchor_avoidance_at_5")
    anchor_avoid = _get_nested(candidate_benchmark, "summary", "mean_anchor_avoidance_at_5")

    baseline_finetune = _get_nested(baseline, "training", "finetune_roc_auc")
    baseline_recall = _get_nested(
        baseline,
        "benchmark",
        scoring_mode,
        "mean_recall_at_5",
        default=_get_nested(baseline, "benchmark", "hybrid", "mean_recall_at_5"),
    )

    champion_finetune = _get_nested(champion, "training", "finetune_roc_auc")
    champion_recall = _get_nested(champion, "benchmark", "mean_recall_at_5")

    checks: list[dict] = []
    passed = True

    def add_check(
        name: str,
        candidate: float | None,
        reference: float | None,
        *,
        required: bool,
        tolerance: float = 0.0,
    ) -> None:
        nonlocal passed
        ok = True
        message = "no reference"
        if candidate is None:
            ok = not required
            message = "missing candidate metric"
        elif reference is not None:
            ok = candidate + min_improvement + tolerance >= reference
            message = f"candidate={candidate:.4f} reference={reference:.4f} tolerance={tolerance:.4f}"
        if required and not ok:
            passed = False
        checks.append({"name": name, "passed": ok, "message": message})

    add_check(
        "finetune_roc_auc_vs_baseline",
        finetune_auc,
        baseline_finetune,
        required=baseline_finetune is not None and finetune_auc is not None,
        tolerance=auc_tolerance,
    )
    add_check(
        "recall_at_5_vs_baseline",
        recall_at_5,
        baseline_recall,
        required=baseline_recall is not None and recall_at_5 is not None,
    )
    add_check(
        "finetune_roc_auc_vs_champion",
        finetune_auc,
        champion_finetune,
        required=champion_finetune is not None and finetune_auc is not None,
        tolerance=auc_tolerance,
    )
    add_check(
        "recall_at_5_vs_champion",
        recall_at_5,
        champion_recall,
        required=champion_recall is not None and recall_at_5 is not None,
    )

    return {
        "passed": passed,
        "promote_model": passed,
        "checks": checks,
        "candidate": {
            "finetune_roc_auc": finetune_auc,
            "statistical_roc_auc": stat_auc,
            "pretrain_roc_auc": pretrain_auc,
            "mean_recall_at_5": recall_at_5,
            "mean_buried_anchor_avoidance_at_5": buried_avoid,
            "mean_anchor_avoidance_at_5": anchor_avoid,
            "scoring_mode": scoring_mode,
        },
        "baseline": baseline,
        "champion": champion,
        "auc_tolerance": auc_tolerance,
    }
