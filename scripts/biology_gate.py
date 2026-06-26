#!/usr/bin/env python3
"""Run biological validity gate on benchmark artifacts."""

from __future__ import annotations

import json
import sys

from pmhc_hotspot.automation.biology_gate import run_biology_gate
from pmhc_hotspot.automation.metrics_gate import load_baseline_metrics
from pmhc_hotspot.automation.paths import (
    BENCHMARK_REPORT_PATH,
    BIOLOGY_REPORT_PATH,
    REPORTS_DIR,
    ensure_artifact_dirs,
)


def main() -> int:
    ensure_artifact_dirs()
    if not BENCHMARK_REPORT_PATH.exists():
        print(f"Missing benchmark report: {BENCHMARK_REPORT_PATH}", file=sys.stderr)
        return 1

    with BENCHMARK_REPORT_PATH.open() as fh:
        benchmark_report = json.load(fh)

    result = run_biology_gate(benchmark_report, baseline=load_baseline_metrics())
    with BIOLOGY_REPORT_PATH.open("w") as fh:
        json.dump(result, fh, indent=2)

    print(f"Biology gate passed: {result['passed']}")
    for check in result["checks"]:
        status = "OK" if check["passed"] else "FAIL"
        print(f"  [{status}] {check['name']}: {check['message']}")
    print(f"Wrote {BIOLOGY_REPORT_PATH}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
