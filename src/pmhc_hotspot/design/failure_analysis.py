"""Failure analysis for design validation (Phase 2.5)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List


def identify_failed_predictions(
    eval_results: List[dict],
    *,
    threshold_pae: float = 0.8,
) -> List[dict]:
    failures = []
    by_pdb: dict[str, list[dict]] = {}
    for row in eval_results:
        by_pdb.setdefault(row.get("pdb_id", "unknown"), []).append(row)

    random_means = {}
    for pdb_id, rows in by_pdb.items():
        random_rows = [r for r in rows if r.get("strategy") == "random"]
        if random_rows:
            random_means[pdb_id] = sum(r.get("interface_pae", 1) for r in random_rows) / len(random_rows)

    for row in eval_results:
        pae = float(row.get("interface_pae", row.get("af2_ipae", 0)))
        pdb_id = row.get("pdb_id", "unknown")
        strategy = row.get("strategy", "")
        hotspot_fail = strategy == "hotspot" and pdb_id in random_means and pae >= random_means[pdb_id]
        if pae > threshold_pae or hotspot_fail:
            failures.append(
                {
                    "pdb_id": pdb_id,
                    "strategy": strategy,
                    "interface_pae": pae,
                    "hotspot_residues_predicted": row.get("hotspot_residues", []),
                    "true_tcr_contact_residues": row.get("true_contacts", []),
                    "recall_at_5": row.get("recall_at_5"),
                    "why_did_it_fail": "high_pae" if pae > threshold_pae else "hotspot_not_better_than_random",
                }
            )
    return failures


def manual_inspection_guide(failed_cases: List[dict], output_html: Path) -> Path:
    lines = ["<html><body><h1>Design failure inspection guide</h1>"]
    for case in failed_cases:
        lines.append("<hr>")
        lines.append(f"<h2>{case.get('pdb_id')} — {case.get('strategy')}</h2>")
        lines.append(f"<p>PAE: {case.get('interface_pae')}</p>")
        lines.append(f"<p>Predicted hotspots: {case.get('hotspot_residues_predicted')}</p>")
        lines.append(f"<p>True TCR contacts: {case.get('true_tcr_contact_residues')}</p>")
        lines.append(f"<p>Hypothesis: {case.get('why_did_it_fail')}</p>")
    lines.append("</body></html>")
    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text("\n".join(lines))
    return output_html


def write_failure_summary(failures: List[dict], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({"failures": failures, "n": len(failures)}, indent=2))
    return output_path
