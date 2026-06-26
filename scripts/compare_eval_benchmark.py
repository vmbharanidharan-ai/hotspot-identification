#!/usr/bin/env python3
"""Compare current eval benchmark against baseline (package improvement gate)."""

from __future__ import annotations

import argparse
import sys

from pmhc_hotspot.automation.metrics_gate import load_json
from pmhc_hotspot.automation.overnight import compare_eval_reports, write_eval_compare
from pmhc_hotspot.automation.paths import (
    EVAL_BASELINE_PATH,
    EVAL_BENCHMARK_REPORT_PATH,
    EVAL_COMPARE_PATH,
    ensure_artifact_dirs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", default=str(EVAL_BENCHMARK_REPORT_PATH))
    parser.add_argument("--baseline", default=str(EVAL_BASELINE_PATH))
    parser.add_argument("--target-recall", type=float, default=0.77)
    args = parser.parse_args()

    ensure_artifact_dirs()
    current = load_json(args.current)
    if not current:
        print(f"Missing current eval report: {args.current}", file=sys.stderr)
        return 1

    baseline = load_json(args.baseline) if args.baseline else {}
    comparison = compare_eval_reports(
        current,
        baseline,
        target_recall=args.target_recall,
    )
    write_eval_compare(current, comparison)

    print(f"Package improved: {comparison['package_improved']}")
    for check in comparison["checks"]:
        status = "OK" if check["passed"] else "FAIL"
        print(f"  [{status}] {check['name']}: {check['message']}")
    print(f"Wrote {EVAL_COMPARE_PATH}")
    return 0 if comparison["package_improved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
