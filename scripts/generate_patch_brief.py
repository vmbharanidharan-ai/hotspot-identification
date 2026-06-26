#!/usr/bin/env python3
"""Generate a single actionable patch brief for Cursor agents."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pmhc_hotspot.automation.metrics_gate import load_json
from pmhc_hotspot.automation.paths import (
    BENCHMARK_REPORT_PATH,
    BIOLOGY_REPORT_PATH,
    EVAL_BENCHMARK_REPORT_PATH,
    METRICS_GATE_PATH,
    PATCH_BRIEF_PATH,
    REPORTS_DIR,
    TRAINING_REPORT_PATH,
    ensure_artifact_dirs,
)

BIOLOGY_RULES = [
    "Biological validity is the highest priority.",
    "Never optimize a metric by breaking biology.",
    "Never predict buried residues as hotspots.",
    "Never mix binding signal with TCR-contact signal.",
    "Prefer conservative false negatives over biologically impossible false positives.",
    "Reject patches that improve benchmark score but weaken structural plausibility.",
]


def _lowest_metric(training: dict, benchmark: dict) -> str:
    finetune = (training.get("finetune_cv") or {}).get("overall", {}).get("roc_auc")
    recall = (benchmark.get("summary") or {}).get("mean_recall_at_5")
    if finetune is not None and finetune < 0.75:
        return "finetune_model_or_features"
    if recall is not None and recall < 0.65:
        return "benchmark_recall_or_ranking"
    return "calibration_or_scoring"


def _biology_issue(biology: dict) -> str | None:
    for check in biology.get("checks", []):
        if not check.get("passed"):
            return check.get("name")
    for violation in biology.get("violations", []):
        return violation.get("issue")
    return None


def main() -> int:
    ensure_artifact_dirs()

    training = load_json(TRAINING_REPORT_PATH)
    benchmark = load_json(BENCHMARK_REPORT_PATH)
    if EVAL_BENCHMARK_REPORT_PATH.exists():
        benchmark = load_json(EVAL_BENCHMARK_REPORT_PATH)
    biology = load_json(BIOLOGY_REPORT_PATH)
    gate = load_json(METRICS_GATE_PATH)

    bottleneck = _lowest_metric(training, benchmark)
    biology_issue = _biology_issue(biology)

    if biology_issue:
        category = "biology"
        recommendation = (
            f"Address biological violation '{biology_issue}' in scoring or feature logic "
            "(SASA exposure, anchor suppression, or concavity) before tuning ML hyperparameters."
        )
    elif bottleneck == "benchmark_recall_or_ranking":
        category = "scoring"
        recommendation = (
            "Improve top-k TCR-contact recovery without weakening buried-anchor avoidance. "
            "Inspect per-structure failures in benchmark_report.json."
        )
    elif bottleneck == "finetune_model_or_features":
        category = "features"
        recommendation = (
            "Improve structural feature quality or grouped CV stability. "
            "Check one feature module (SASA, contacts, or geometry) only."
        )
    else:
        category = "calibration"
        recommendation = (
            "Tune statistical calibration or hybrid blending while preserving deterministic baseline behavior."
        )

    brief = {
        "task": "Propose one minimal package code improvement based on the latest automation artifacts.",
        "bottleneck_category": category,
        "recommendation": recommendation,
        "biology_rules": BIOLOGY_RULES,
        "rules": [
            "Edit only one subsystem.",
            "Add or update at least one unit test.",
            "Do not modify training data files or artifact binaries.",
            "Do not change package metadata unless required.",
            "Stop if the fix requires more than one subsystem.",
            "No more than one accepted patch per cycle.",
        ],
        "artifacts": {
            "training_report": str(TRAINING_REPORT_PATH),
            "benchmark_report": str(BENCHMARK_REPORT_PATH),
            "biology_gate": str(BIOLOGY_REPORT_PATH),
            "metrics_gate": str(METRICS_GATE_PATH),
        },
        "gate_status": gate.get("status"),
        "promote_model": gate.get("promote_model"),
    }

    with PATCH_BRIEF_PATH.open("w") as fh:
        json.dump(brief, fh, indent=2)

    log_path = REPORTS_DIR / "patch_proposal_log.jsonl"
    with log_path.open("a") as fh:
        fh.write(json.dumps({"brief": brief}) + "\n")

    print(f"Category: {category}")
    print(f"Recommendation: {recommendation}")
    print(f"Wrote {PATCH_BRIEF_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
