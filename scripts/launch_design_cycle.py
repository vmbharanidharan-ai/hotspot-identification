#!/usr/bin/env python3
"""
Launch binder-conditioning pipeline phases with Cursor SDK agents.

IDE mode (no API key): open this repo in Cursor and ask the orchestrator subagent
to run a cycle — see docs/DESIGN_PIPELINE_RUNBOOK.md.

SDK mode (API key required):
  export CURSOR_API_KEY=...
  pip install cursor-sdk
  python scripts/launch_design_cycle.py ingest
  python scripts/launch_design_cycle.py --all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from pmhc_hotspot.automation.cursor_agents import PHASE_AGENTS, run_cycle_sdk, run_phase_sdk  # noqa: E402


DEFAULT_SEQUENCE = ["ingest", "features", "design-export", "design-eval", "gatekeeper"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "phase",
        nargs="?",
        choices=[*PHASE_AGENTS.keys(), "all"],
        default="all",
        help="Pipeline phase to run via SDK agent",
    )
    parser.add_argument("--model", default="composer-2.5", help="Cursor model id")
    parser.add_argument("--dry-run", action="store_true", help="Print prompt only")
    args = parser.parse_args()

    phases = DEFAULT_SEQUENCE if args.phase == "all" else [args.phase]

    if args.dry_run:
        from pmhc_hotspot.automation.cursor_agents import build_phase_prompt

        for phase in phases:
            dispatch = build_phase_prompt(phase)
            print(f"=== {phase} ({dispatch.agent_name}) ===\n{dispatch.prompt[:800]}...\n")
        return 0

    try:
        if len(phases) == 1:
            result = run_phase_sdk(phases[0], model=args.model, stream=True)
            print(result)
        else:
            for phase, text in run_cycle_sdk(phases, model=args.model):
                print(f"\n===== {phase} =====\n{text}\n")
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print(
            "\nTip: Phase 1 ingest does not need the SDK — run:\n"
            "  pmhc-hotspot build-dataset --config configs/dataset.yaml\n",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
