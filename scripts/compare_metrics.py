#!/usr/bin/env python3
"""Compare candidate metrics against baseline/champion and decide promotion."""

from __future__ import annotations

import json
import sys

from pmhc_hotspot.automation.biology_gate import run_biology_gate
from pmhc_hotspot.automation.metrics_gate import compare_metrics, load_baseline_metrics, load_json
from pmhc_hotspot.automation.paths import (
    BENCHMARK_REPORT_PATH,
    BIOLOGY_REPORT_PATH,
    CHAMPION_META_PATH,
    METRICS_GATE_PATH,
    TRAINING_REPORT_PATH,
    ensure_artifact_dirs,
)


def main() -> int:
    ensure_artifact_dirs()

    training_report = load_json(TRAINING_REPORT_PATH)
    benchmark_report = load_json(BENCHMARK_REPORT_PATH)
    champion = load_json(CHAMPION_META_PATH)
    baseline = load_baseline_metrics()

    metrics_result = compare_metrics(
        training_report=training_report,
        benchmark_report=benchmark_report,
        baseline=baseline,
        champion=champion,
    )

    biology_result = load_json(BIOLOGY_REPORT_PATH)
    if not biology_result and benchmark_report:
        biology_result = run_biology_gate(benchmark_report, baseline=baseline)
        with BIOLOGY_REPORT_PATH.open("w") as fh:
            json.dump(biology_result, fh, indent=2)

    promote = metrics_result["passed"] and biology_result.get("passed", False)
    payload = {
        "metrics": metrics_result,
        "biology": biology_result,
        "promote_model": promote,
        "status": "ok" if promote else "reject",
    }
    with METRICS_GATE_PATH.open("w") as fh:
        json.dump(payload, fh, indent=2)

    print(f"Metrics gate passed: {metrics_result['passed']}")
    print(f"Biology gate passed: {biology_result.get('passed', False)}")
    print(f"Promote model: {promote}")
    for check in metrics_result["checks"]:
        status = "OK" if check["passed"] else "FAIL"
        print(f"  [{status}] {check['name']}: {check['message']}")
    print(f"Wrote {METRICS_GATE_PATH}")
    return 0 if promote else 1


if __name__ == "__main__":
    raise SystemExit(main())
