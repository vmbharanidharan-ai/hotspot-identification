"""Biological validity checks for benchmark predictions."""

from __future__ import annotations

from typing import Any


def run_biology_gate(
    benchmark_report: dict,
    *,
    baseline: dict | None = None,
    min_buried_anchor_avoidance: float | None = None,
    min_anchor_avoidance: float | None = None,
    max_buried_in_top5: int = 0,
) -> dict:
    """
    Fail if predictions violate structural plausibility constraints.

    Biological validity overrides metric chasing: a run fails if top-ranked
    residues include buried anchors or anchor avoidance drops below baseline.
    """
    baseline = baseline or {}
    biology_baseline = baseline.get("biology", {})

    min_buried = min_buried_anchor_avoidance
    if min_buried is None:
        min_buried = float(biology_baseline.get("min_buried_anchor_avoidance_at_5", 0.85))

    min_anchor = min_anchor_avoidance
    if min_anchor is None:
        min_anchor = float(biology_baseline.get("min_anchor_avoidance_at_5", 0.80))

    summary = benchmark_report.get("summary", {})
    results: list[dict[str, Any]] = benchmark_report.get("results", [])

    mean_buried = summary.get("mean_buried_anchor_avoidance_at_5")
    mean_anchor = summary.get("mean_anchor_avoidance_at_5")

    violations: list[dict] = []
    for row in results:
        if row.get("skipped"):
            continue
        pdb_id = row.get("pdb_id", "?")
        buried_avoid = (row.get("buried_anchor_avoidance_at_k") or {}).get(5)
        if buried_avoid is not None and buried_avoid < min_buried:
            violations.append(
                {
                    "pdb_id": pdb_id,
                    "issue": "low_buried_anchor_avoidance",
                    "value": buried_avoid,
                    "threshold": min_buried,
                }
            )
        anchor_avoid = (row.get("anchor_avoidance_at_k") or {}).get(5)
        if anchor_avoid is not None and anchor_avoid < min_anchor:
            violations.append(
                {
                    "pdb_id": pdb_id,
                    "issue": "low_anchor_avoidance",
                    "value": anchor_avoid,
                    "threshold": min_anchor,
                }
            )

    passed = True
    checks: list[dict] = []

    def add_threshold_check(name: str, value: float | None, threshold: float) -> None:
        nonlocal passed
        if value is None or value != value:
            checks.append({"name": name, "passed": False, "message": "missing metric"})
            passed = False
            return
        ok = value >= threshold
        if not ok:
            passed = False
        checks.append(
            {
                "name": name,
                "passed": ok,
                "message": f"value={value:.4f} threshold={threshold:.4f}",
            }
        )

    add_threshold_check("mean_buried_anchor_avoidance_at_5", mean_buried, min_buried)
    add_threshold_check("mean_anchor_avoidance_at_5", mean_anchor, min_anchor)

    if len(violations) > max_buried_in_top5:
        passed = False
        checks.append(
            {
                "name": "per_structure_violations",
                "passed": False,
                "message": f"{len(violations)} structure-level violations",
            }
        )
    else:
        checks.append(
            {
                "name": "per_structure_violations",
                "passed": True,
                "message": f"{len(violations)} violations (max {max_buried_in_top5})",
            }
        )

    return {
        "passed": passed,
        "checks": checks,
        "violations": violations,
        "summary": {
            "mean_buried_anchor_avoidance_at_5": mean_buried,
            "mean_anchor_avoidance_at_5": mean_anchor,
            "n_structures": summary.get("n_structures", 0),
        },
        "thresholds": {
            "min_buried_anchor_avoidance_at_5": min_buried,
            "min_anchor_avoidance_at_5": min_anchor,
        },
    }
