#!/usr/bin/env python3
"""
Overnight package-improvement controller.

Runs metrics/gates, prepares Cursor agent prompts, and optionally invokes
Cursor SDK agents in parallel (Analyst + Biology Reviewer) then sequential
(Patcher → Reviewer).

Package-first default: eval fixed 11-PDB manifest with the current default
model — retrain only when PMHC_OVERNIGHT_RETRAIN=1.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pmhc_hotspot.automation.cursor_agents import launch_parallel, sdk_available
from pmhc_hotspot.automation.overnight import (
    compare_eval_reports,
    parse_reviewer_verdict,
    prepare_agent_prompts,
    run_pytest,
    should_attempt_code_patch,
    update_overnight_state,
    weak_eval_structures,
    write_eval_compare,
)
from pmhc_hotspot.automation.paths import (
    AGENT_OUTPUTS_DIR,
    EVAL_BASELINE_PATH,
    EVAL_BENCHMARK_REPORT_PATH,
    EVAL_COMPARE_PATH,
    PATCH_BRIEF_PATH,
    REPO_ROOT,
    ensure_artifact_dirs,
)
from pmhc_hotspot.automation.biology_gate import run_biology_gate
from pmhc_hotspot.automation.metrics_gate import load_baseline_metrics, load_json


def _run_script(name: str, *args: str) -> int:
    script = REPO_ROOT / "scripts" / name
    result = subprocess.run([sys.executable, str(script), *args], cwd=str(REPO_ROOT))
    return result.returncode


def _brief_extra(patch_brief: dict) -> str:
    return "Current patch brief (JSON):\n```json\n" + json.dumps(patch_brief, indent=2) + "\n```"


def _generate_package_patch_brief(eval_report: dict, biology_report: dict) -> dict:
    weak = weak_eval_structures(eval_report)
    recall = (eval_report.get("summary") or {}).get("mean_recall_at_5")
    det_recall = (eval_report.get("deterministic_summary") or {}).get("mean_recall_at_5")

    if not biology_report.get("passed", True):
        category = "biology"
        recommendation = (
            "Fix biological plausibility in scoring/features before any recall tuning. "
            "See biology_gate.json and per-structure predictions."
        )
    elif weak:
        category = "scoring"
        failing = ", ".join(row["pdb_id"] for row in weak[:5])
        recommendation = (
            f"Improve top-k TCR-contact recovery on eval PDB(s): {failing}. "
            "Edit one subsystem (features, scoring, or inference). "
            f"Current hybrid recall@5={recall:.3f}, deterministic={det_recall:.3f}."
        )
    else:
        category = "none"
        recommendation = "No code patch required this cycle; eval and biology gates look acceptable."

    return {
        "task": "Improve the pmhc-hotspot PACKAGE CODE (not just retrain the model).",
        "mode": "package_first",
        "bottleneck_category": category,
        "recommendation": recommendation,
        "weak_eval_structures": weak,
        "eval_summary": eval_report.get("summary", {}),
        "biology_passed": biology_report.get("passed"),
        "rules": [
            "Biological validity is the highest priority.",
            "Edit only one subsystem.",
            "Add or update at least one unit test.",
            "Do not modify training data, manifests, or .joblib artifacts.",
            "Do not retrain models — improve code and re-run eval benchmark.",
            "Stop if the fix spans multiple subsystems.",
        ],
        "artifacts": {
            "eval_benchmark_report": str(EVAL_BENCHMARK_REPORT_PATH),
            "eval_baseline": str(EVAL_BASELINE_PATH),
        },
    }


def phase_metrics(*, save_baseline: bool, retrain: bool) -> dict:
    ensure_artifact_dirs()
    report: dict = {"phase": "metrics", "steps": []}

    if retrain:
        code = _run_script("fetch_iedb.py")
        report["steps"].append({"step": "fetch_iedb", "code": code})
        if code != 0:
            os.environ.setdefault("PMHC_ALLOW_SMOKE_TRAIN", "1")
            _run_script("fetch_iedb.py")
        report["steps"].append({"step": "train_once", "code": _run_script("train_once.py")})

    eval_args = ["--save-baseline"] if save_baseline else []
    code = _run_script("eval_package_benchmark.py", *eval_args)
    report["steps"].append({"step": "eval_package_benchmark", "code": code})
    if code != 0:
        report["status"] = "failed"
        return report

    eval_report = load_json(EVAL_BENCHMARK_REPORT_PATH)
    biology = run_biology_gate(eval_report, baseline=load_baseline_metrics())
    biology_path = REPO_ROOT / "artifacts/reports/biology_gate.json"
    biology_path.parent.mkdir(parents=True, exist_ok=True)
    with biology_path.open("w") as fh:
        json.dump(biology, fh, indent=2)

    brief = _generate_package_patch_brief(eval_report, biology)
    with PATCH_BRIEF_PATH.open("w") as fh:
        json.dump(brief, fh, indent=2)

    report["eval_recall_at_5"] = (eval_report.get("summary") or {}).get("mean_recall_at_5")
    report["biology_passed"] = biology.get("passed")
    report["patch_category"] = brief.get("bottleneck_category")
    report["attempt_code_patch"] = should_attempt_code_patch(eval_report, biology)
    report["status"] = "ok"
    return report


def phase_agents(patch_brief: dict, *, attempt_patch: bool) -> dict:
    ensure_artifact_dirs()
    prompts = prepare_agent_prompts(patch_brief=patch_brief)
    extra = _brief_extra(patch_brief)
    report: dict = {
        "phase": "agents",
        "sdk_available": sdk_available(),
        "prompts": {k: str(v) for k, v in prompts.items()},
        "runs": [],
    }

    if not sdk_available():
        report["status"] = "manual"
        report["message"] = (
            "Set CURSOR_API_KEY and pip install -e '.[automation]', OR in Cursor IDE invoke "
            "the overnight-orchestrator subagent — it launches analyst + biology-reviewer "
            "in parallel. Prompt files: artifacts/reports/agent_prompts/*_full.md"
        )
        update_overnight_state(agent_phase=report)
        return report

    parallel = launch_parallel(
        ["analyst", "biology_reviewer"],
        extra_by_role={"analyst": extra, "biology_reviewer": extra},
    )
    report["runs"].extend(parallel)

    biology_out = AGENT_OUTPUTS_DIR / "biology_reviewer.txt"
    if biology_out.exists() and "FAIL" in biology_out.read_text().upper():
        report["status"] = "biology_rejected"
        report["message"] = "Biology reviewer failed — skipping patcher."
        update_overnight_state(agent_phase=report)
        return report

    if not attempt_patch or patch_brief.get("bottleneck_category") == "none":
        report["status"] = "no_patch_needed"
        report["message"] = "Eval/biology acceptable — no patcher run."
        update_overnight_state(agent_phase=report)
        return report

    patcher_results = launch_parallel(["patcher"], extra_by_role={"patcher": extra})
    report["runs"].extend(patcher_results)

    reviewer_results = launch_parallel(["reviewer"])
    report["runs"].extend(reviewer_results)

    reviewer_text = ""
    reviewer_path = AGENT_OUTPUTS_DIR / "reviewer.txt"
    if reviewer_path.exists():
        reviewer_text = reviewer_path.read_text()
    verdict = parse_reviewer_verdict(reviewer_text)
    report["reviewer_verdict"] = verdict
    report["status"] = "approved" if verdict == "APPROVE" else "rejected_or_unknown"
    update_overnight_state(agent_phase=report)
    return report


def phase_validate(*, save_baseline: bool = False) -> dict:
    ensure_artifact_dirs()
    report: dict = {"phase": "validate", "steps": []}

    pytest_result = run_pytest()
    report["steps"].append(
        {
            "step": "pytest",
            "code": pytest_result.returncode,
            "stdout_tail": pytest_result.stdout[-2000:],
            "stderr_tail": pytest_result.stderr[-2000:],
        }
    )
    if pytest_result.returncode != 0:
        report["status"] = "failed"
        return report

    eval_args = ["--save-baseline"] if save_baseline else []
    code = _run_script("eval_package_benchmark.py", *eval_args)
    report["steps"].append({"step": "eval_package_benchmark", "code": code})
    if code != 0:
        report["status"] = "failed"
        return report

    current = load_json(EVAL_BENCHMARK_REPORT_PATH)
    baseline = load_json(EVAL_BASELINE_PATH)
    comparison = compare_eval_reports(current, baseline)
    write_eval_compare(current, comparison)
    report["comparison"] = comparison
    report["status"] = "ok" if comparison["package_improved"] else "no_improvement"
    update_overnight_state(validate_phase=report, package_improved=comparison["package_improved"])
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase",
        choices=["all", "metrics", "agents", "validate"],
        default=os.environ.get("PMHC_OVERNIGHT_PHASE", "all"),
    )
    parser.add_argument("--cycle", type=int, default=int(os.environ.get("PMHC_OVERNIGHT_CYCLE", "1")))
    parser.add_argument(
        "--retrain",
        action="store_true",
        default=os.environ.get("PMHC_OVERNIGHT_RETRAIN", "").lower() in {"1", "true", "yes"},
    )
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        default=os.environ.get("PMHC_OVERNIGHT_SAVE_BASELINE", "").lower() in {"1", "true", "yes"},
    )
    parser.add_argument(
        "--skip-agents",
        action="store_true",
        default=os.environ.get("PMHC_OVERNIGHT_SKIP_AGENTS", "").lower() in {"1", "true", "yes"},
    )
    args = parser.parse_args()

    ensure_artifact_dirs()
    update_overnight_state(cycle=args.cycle, phase=args.phase, started=True)

    summary: dict = {"cycle": args.cycle, "phases": {}}

    if args.phase in {"all", "metrics"}:
        metrics_report = phase_metrics(save_baseline=args.save_baseline, retrain=args.retrain)
        summary["phases"]["metrics"] = metrics_report
        if metrics_report.get("status") == "failed":
            print(json.dumps(summary, indent=2))
            return 1

    if args.phase in {"all", "agents"} and not args.skip_agents:
        brief = load_json(PATCH_BRIEF_PATH)
        eval_report = load_json(EVAL_BENCHMARK_REPORT_PATH)
        biology = load_json(REPO_ROOT / "artifacts/reports/biology_gate.json")
        attempt = should_attempt_code_patch(eval_report, biology)
        agents_report = phase_agents(brief, attempt_patch=attempt)
        summary["phases"]["agents"] = agents_report

        if args.phase == "all" and agents_report.get("status") not in {
            "approved",
            "no_patch_needed",
            "manual",
        }:
            print(json.dumps(summary, indent=2))
            return 0

    if args.phase in {"all", "validate"}:
        validate_report = phase_validate(save_baseline=False)
        summary["phases"]["validate"] = validate_report
        print(json.dumps(summary, indent=2))
        if validate_report.get("status") == "failed":
            return 1
        if validate_report.get("status") == "no_improvement":
            return 2
        return 0

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
