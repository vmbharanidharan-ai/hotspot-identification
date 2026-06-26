#!/usr/bin/env python3
"""CLI entry for parallel Cursor SDK agents (see automation/cursor_agents.py)."""

from __future__ import annotations

import argparse
import json
import sys

from pmhc_hotspot.automation.cursor_agents import launch_parallel, sdk_available
from pmhc_hotspot.automation.metrics_gate import load_json
from pmhc_hotspot.automation.overnight import (
    parse_reviewer_verdict,
    should_attempt_code_patch,
    update_overnight_state,
)
from pmhc_hotspot.automation.paths import (
    AGENT_OUTPUTS_DIR,
    EVAL_BENCHMARK_REPORT_PATH,
    PATCH_BRIEF_PATH,
    REPO_ROOT,
    ensure_artifact_dirs,
)


def _brief_extra(patch_brief: dict) -> str:
    return "Current patch brief (JSON):\n```json\n" + json.dumps(patch_brief, indent=2) + "\n```"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["parallel", "sequential", "all"], default="all")
    args = parser.parse_args()
    ensure_artifact_dirs()

    if not sdk_available():
        print(
            "CURSOR_API_KEY not set or cursor-sdk not installed.\n"
            "Install: pip install -e '.[automation]'\n"
            "In Cursor IDE: use the overnight-orchestrator subagent — it launches\n"
            "  analyst + biology-reviewer in parallel via native subagent delegation.",
            file=sys.stderr,
        )
        return 1

    brief = load_json(PATCH_BRIEF_PATH)
    extra = _brief_extra(brief)
    report: dict = {"phase": args.phase, "runs": []}

    if args.phase in {"parallel", "all"}:
        parallel = launch_parallel(
            ["analyst", "biology_reviewer"],
            extra_by_role={"analyst": extra, "biology_reviewer": extra},
        )
        report["parallel"] = parallel
        bio_path = AGENT_OUTPUTS_DIR / "biology_reviewer.txt"
        if bio_path.exists() and "FAIL" in bio_path.read_text().upper():
            update_overnight_state(parallel_agents=report, biology_failed=True)
            print(json.dumps(report, indent=2))
            return 1

    if args.phase in {"sequential", "all"}:
        eval_report = load_json(EVAL_BENCHMARK_REPORT_PATH)
        biology = load_json(REPO_ROOT / "artifacts/reports/biology_gate.json")
        bio_review = REPO_ROOT / "artifacts/reports/biology_review.md"
        if bio_review.exists() and "FAIL" in bio_review.read_text().upper():
            biology["passed"] = False
        if not should_attempt_code_patch(eval_report, biology) or brief.get("bottleneck_category") == "none":
            report["sequential"] = {"skipped": True}
            update_overnight_state(parallel_agents=report)
            print(json.dumps(report, indent=2))
            return 0

        report["sequential"] = {
            "patcher": launch_parallel(["patcher"], extra_by_role={"patcher": extra}),
            "reviewer": launch_parallel(["reviewer"]),
        }
        rev_path = AGENT_OUTPUTS_DIR / "reviewer.txt"
        if rev_path.exists():
            report["reviewer_verdict"] = parse_reviewer_verdict(rev_path.read_text())

    update_overnight_state(parallel_agents=report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
