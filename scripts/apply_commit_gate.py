#!/usr/bin/env python3
"""Apply commit-gate agent decision — commit only on APPROVE_COMMIT."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from pmhc_hotspot.automation.paths import REPO_ROOT

DECISION_PATH = REPO_ROOT / "artifacts/reports/commit_gate_decision.md"
FORBIDDEN_PATTERNS = (
    r"\.env",
    r"credentials",
    r"\.joblib$",
    r"training_manifest\.yaml",
    r"data/training",
)


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


def parse_decision(text: str) -> tuple[str, str]:
    lines = [ln.rstrip() for ln in text.strip().splitlines()]
    if not lines:
        return "UNKNOWN", ""
    first = lines[0].upper()
    if first.startswith("APPROVE_COMMIT"):
        verdict = "APPROVE_COMMIT"
    elif first.startswith("REJECT_COMMIT"):
        verdict = "REJECT_COMMIT"
    else:
        verdict = "UNKNOWN"

    # Prefer first line inside ``` fenced block as commit message
    in_fence = False
    for ln in lines[1:]:
        if ln.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence and ln.strip():
            return verdict, ln.strip()

    for ln in lines[1:]:
        stripped = ln.strip()
        if not stripped or stripped.startswith(("#", "-", "|")):
            continue
        if stripped.upper().startswith(("APPROVE", "REJECT", "PROPOSED")):
            continue
        return verdict, stripped.strip("`\"")
    return verdict, "Improve pmhc-hotspot package per overnight cycle"


def forbidden_paths_in_diff() -> list[str]:
    diff = _git("diff", "--name-only", "HEAD")
    if diff.returncode != 0:
        return []
    bad = []
    for path in diff.stdout.splitlines():
        for pat in FORBIDDEN_PATTERNS:
            if re.search(pat, path):
                bad.append(path)
                break
    return bad


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not DECISION_PATH.exists():
        print("No commit_gate_decision.md — skipping commit.", file=sys.stderr)
        return 0

    verdict, message = parse_decision(DECISION_PATH.read_text())
    if verdict != "APPROVE_COMMIT":
        print(f"Commit gate: {verdict} — no commit.")
        return 0

    status = _git("status", "--porcelain")
    if not status.stdout.strip():
        print("Commit gate APPROVE but working tree clean — nothing to commit.")
        return 0

    bad = forbidden_paths_in_diff()
    if bad:
        print(f"Commit blocked — forbidden paths in diff: {bad}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"DRY RUN would commit: {message}")
        _git("diff", "--stat")
        return 0

    add = _git("add", "-A")
    if add.returncode != 0:
        print(add.stderr, file=sys.stderr)
        return add.returncode

    commit = _git("commit", "-m", message)
    if commit.returncode != 0:
        print(commit.stderr, file=sys.stderr)
        return commit.returncode

    print(f"Committed: {message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
