"""Overnight package-improvement loop helpers."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pmhc_hotspot.automation.paths import (
    AGENTS_DIR,
    AGENT_OUTPUTS_DIR,
    AGENT_PROMPTS_DIR,
    EVAL_BASELINE_PATH,
    EVAL_BENCHMARK_REPORT_PATH,
    EVAL_COMPARE_PATH,
    OVERNIGHT_STATE_PATH,
    PATCH_BRIEF_PATH,
    REPO_ROOT,
    ensure_artifact_dirs,
)

TARGET_RECALL_AT_5 = 0.77
RECALL_TOLERANCE = 0.01

ROLE_FILES = {
    "analyst": "analyst.md",
    "biology_reviewer": "biology-reviewer.md",
    "patcher": "patcher.md",
    "reviewer": "reviewer.md",
}


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text.strip()


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open() as fh:
        return json.load(fh)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        json.dump(payload, fh, indent=2)


def build_agent_prompt(role_file: str, *, extra: str = "") -> str:
    preamble = (AGENTS_DIR / "00_shared_preamble.md").read_text()
    role = _strip_frontmatter((AGENTS_DIR / role_file).read_text())
    parts = [preamble.strip(), role]
    if extra.strip():
        parts.append(extra.strip())
    return "\n\n---\n\n".join(parts) + "\n"


def prepare_agent_prompts(*, patch_brief: dict | None = None) -> dict[str, Path]:
    """Write full prompts for each agent role to artifacts/reports/agent_prompts/."""
    ensure_artifact_dirs()
    AGENT_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    brief_text = ""
    if patch_brief:
        brief_text = (
            "Current patch brief (JSON):\n```json\n"
            + json.dumps(patch_brief, indent=2)
            + "\n```"
        )
    paths: dict[str, Path] = {}
    for role, role_file in ROLE_FILES.items():
        extra = brief_text if role in {"analyst", "biology_reviewer", "patcher", "reviewer"} else ""
        prompt = build_agent_prompt(role_file, extra=extra)
        out = AGENT_PROMPTS_DIR / f"{role}_full.md"
        out.write_text(prompt)
        paths[role] = out
    return paths


def weak_eval_structures(benchmark_report: dict, *, recall_threshold: float = 0.5) -> list[dict]:
    """Return per-structure eval failures for analyst context."""
    weak = []
    for row in benchmark_report.get("results", []):
        if row.get("skipped"):
            continue
        recall = (row.get("recall_at_k") or {}).get(5)
        if recall is None or recall != recall or recall < recall_threshold:
            weak.append(
                {
                    "pdb_id": row.get("pdb_id"),
                    "recall_at_5": recall,
                    "peptide_length": row.get("peptide_length"),
                    "predicted_top5": row.get("predicted_top5"),
                    "truth_positions": row.get("truth_positions"),
                }
            )
    return weak


def should_attempt_code_patch(benchmark_report: dict, biology_report: dict) -> bool:
    if not biology_report.get("passed", False):
        return False
    recall = (benchmark_report.get("summary") or {}).get("mean_recall_at_5")
    if recall is None or recall != recall:
        return True
    return recall + RECALL_TOLERANCE < TARGET_RECALL_AT_5


def compare_eval_reports(
    current: dict,
    baseline: dict | None = None,
    *,
    target_recall: float = TARGET_RECALL_AT_5,
    tolerance: float = RECALL_TOLERANCE,
) -> dict:
    baseline = baseline or {}
    base_summary = baseline.get("summary") or {}
    cur_summary = current.get("summary") or {}

    base_recall = base_summary.get("mean_recall_at_5")
    cur_recall = cur_summary.get("mean_recall_at_5")
    base_buried = base_summary.get("mean_buried_anchor_avoidance_at_5")
    cur_buried = cur_summary.get("mean_buried_anchor_avoidance_at_5")

    package_improved = False
    checks: list[dict[str, Any]] = []

    if cur_recall is None or cur_recall != cur_recall:
        checks.append({"name": "recall_at_5", "passed": False, "message": "missing current recall"})
    elif base_recall is None or base_recall != base_recall:
        package_improved = cur_recall >= target_recall - tolerance
        checks.append(
            {
                "name": "recall_at_5_vs_target",
                "passed": package_improved,
                "message": f"current={cur_recall:.4f} target={target_recall:.4f}",
            }
        )
    else:
        improved = cur_recall + tolerance >= base_recall
        at_target = cur_recall >= target_recall - tolerance
        package_improved = improved and at_target
        checks.append(
            {
                "name": "recall_at_5_vs_baseline",
                "passed": improved,
                "message": f"current={cur_recall:.4f} baseline={base_recall:.4f}",
            }
        )
        checks.append(
            {
                "name": "recall_at_5_vs_target",
                "passed": at_target,
                "message": f"current={cur_recall:.4f} target={target_recall:.4f}",
            }
        )

    if cur_buried is not None and cur_buried == cur_buried:
        biology_ok = cur_buried >= 0.85
        if not biology_ok:
            package_improved = False
        checks.append(
            {
                "name": "buried_anchor_avoidance",
                "passed": biology_ok,
                "message": f"value={cur_buried:.4f}",
            }
        )

    return {
        "package_improved": package_improved,
        "checks": checks,
        "current_recall_at_5": cur_recall,
        "baseline_recall_at_5": base_recall,
        "target_recall_at_5": target_recall,
    }


def parse_reviewer_verdict(text: str) -> str:
    upper = text.upper()
    if "APPROVE" in upper and "REJECT" not in upper.split("APPROVE")[0]:
        return "APPROVE"
    if re.search(r"\bREJECT\b", upper):
        return "REJECT"
    return "UNKNOWN"


def run_pytest(repo_root: Path | None = None) -> subprocess.CompletedProcess:
    root = repo_root or REPO_ROOT
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )


def update_overnight_state(**fields) -> dict:
    ensure_artifact_dirs()
    state = load_json(OVERNIGHT_STATE_PATH)
    state.update(fields)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(OVERNIGHT_STATE_PATH, state)
    return state


def save_eval_baseline_if_missing(report: dict) -> None:
    if not EVAL_BASELINE_PATH.exists():
        write_json(EVAL_BASELINE_PATH, report)


def write_eval_compare(current: dict, comparison: dict) -> None:
    write_json(
        EVAL_COMPARE_PATH,
        {
            "comparison": comparison,
            "current_eval": {
                "mean_recall_at_5": (current.get("summary") or {}).get("mean_recall_at_5"),
                "mean_buried_anchor_avoidance_at_5": (
                    (current.get("summary") or {}).get("mean_buried_anchor_avoidance_at_5")
                ),
            },
        },
    )
