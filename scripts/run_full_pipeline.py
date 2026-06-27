#!/usr/bin/env python3
"""Full pipeline orchestrator — runs phases 0–2 locally, stubs HPC phases."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> int:
    print("+", " ".join(cmd))
    return subprocess.call(cmd, cwd=REPO)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "phase",
        choices=["0", "1", "2", "pipeline", "all"],
        default="pipeline",
        nargs="?",
    )
    args = parser.parse_args()

    py = sys.executable
    steps = {
        "0": [
            [py, "-m", "pmhc_hotspot.cli", "crawl-pdb", "--pdb-id", "1BD2", "--pdb-id", "3UTT"],
            [py, "-m", "pmhc_hotspot.cli", "label-contacts", "--workers", "1"],
            [py, "-m", "pytest", "tests/test_phase0.py", "-q"],
        ],
        "1": [
            [py, "-m", "pmhc_hotspot.cli", "expand-dataset"],
            [py, "-m", "pmhc_hotspot.cli", "build-dataset", "--config", "configs/dataset.yaml"],
        ],
        "2": [
            [py, "-m", "pmhc_hotspot.cli", "export-design", "--config", "configs/design.yaml"],
            [py, "-m", "pmhc_hotspot.cli", "run-design-validation", "--config", "configs/eval.yaml"],
        ],
    }

    if args.phase == "all":
        for key in ("0", "1", "2"):
            for cmd in steps[key]:
                if _run(cmd) != 0:
                    return 1
        return 0

    if args.phase == "pipeline":
        for cmd in steps["0"] + steps["1"][:1] + steps["2"]:
            if _run(cmd) != 0:
                return 1
        return 0

    for cmd in steps[args.phase]:
        if _run(cmd) != 0:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
