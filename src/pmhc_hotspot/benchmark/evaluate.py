"""Benchmark evaluation metrics and aggregation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from pmhc_hotspot.benchmark.metrics import HotspotEvaluator
from pmhc_hotspot.features.allele_rules import get_anchor_positions, normalize_allele


@dataclass
class StructureEvaluation:
    pdb_id: str
    allele: str | None
    peptide_length: int
    n_truth_contacts: int
    recall_at_k: dict[int, float] = field(default_factory=dict)
    precision_at_k: dict[int, float] = field(default_factory=dict)
    anchor_avoidance_at_k: dict[int, float] = field(default_factory=dict)
    buried_anchor_avoidance_at_k: dict[int, float] = field(default_factory=dict)
    patch_contiguity_at_k: dict[int, float] = field(default_factory=dict)
    truth_positions: list[str] = field(default_factory=list)
    predicted_top5: list[str] = field(default_factory=list)
    skipped: bool = False
    error: str = ""


def _position_index(position: str) -> int:
    return int(position.lstrip("P")) - 1


def evaluate_structure(
    *,
    pdb_id: str,
    predicted_ordered: list[str],
    truth_positions: set[str],
    allele: str | None,
    peptide_length: int,
    top_k: tuple[int, ...] = (1, 3, 5),
    buried_anchor_positions: set[str] | None = None,
) -> StructureEvaluation:
    norm_allele = normalize_allele(allele)
    anchor_positions = {
        f"P{p}" for p in get_anchor_positions(norm_allele, peptide_length)
    }
    truth = set(truth_positions)

    ev = StructureEvaluation(
        pdb_id=pdb_id,
        allele=norm_allele,
        peptide_length=peptide_length,
        n_truth_contacts=len(truth),
        truth_positions=sorted(truth),
        predicted_top5=predicted_ordered[:5],
    )

    for k in top_k:
        top_preds = set(predicted_ordered[:k])
        pred_indices = [_position_index(p) for p in predicted_ordered[:k]]
        anchor_numeric = {int(p.lstrip("P")) for p in anchor_positions}

        if truth:
            tp = len(top_preds & truth)
            ev.recall_at_k[k] = tp / len(truth)
            ev.precision_at_k[k] = tp / k
        else:
            ev.recall_at_k[k] = float("nan")
            ev.precision_at_k[k] = float("nan")

        ev.anchor_avoidance_at_k[k] = HotspotEvaluator.anchor_avoidance(
            {int(p.lstrip("P")) for p in top_preds},
            anchor_numeric,
        )
        if buried_anchor_positions:
            buried_numeric = {int(p.lstrip("P")) for p in buried_anchor_positions}
            ev.buried_anchor_avoidance_at_k[k] = HotspotEvaluator.anchor_avoidance(
                {int(p.lstrip("P")) for p in top_preds},
                buried_numeric,
            )
        ev.patch_contiguity_at_k[k] = HotspotEvaluator.patch_contiguity(pred_indices)

    return ev


def aggregate_results(results: list[StructureEvaluation]) -> dict:
    valid = [r for r in results if not r.skipped and r.n_truth_contacts > 0]
    if not valid:
        return {"n_structures": 0, "message": "No valid benchmark results"}

    def mean_metric(attr: str, k: int) -> float:
        vals = [getattr(r, attr)[k] for r in valid if k in getattr(r, attr)]
        vals = [v for v in vals if v == v]  # drop nan
        return sum(vals) / len(vals) if vals else float("nan")

    summary = {
        "n_structures": len(valid),
        "n_skipped": sum(1 for r in results if r.skipped),
        "mean_recall_at_3": mean_metric("recall_at_k", 3),
        "mean_recall_at_5": mean_metric("recall_at_k", 5),
        "mean_precision_at_5": mean_metric("precision_at_k", 5),
        "mean_anchor_avoidance_at_5": mean_metric("anchor_avoidance_at_k", 5),
        "mean_buried_anchor_avoidance_at_5": mean_metric("buried_anchor_avoidance_at_k", 5),
        "mean_patch_contiguity_at_5": mean_metric("patch_contiguity_at_k", 5),
    }

    by_length: dict[str, list[StructureEvaluation]] = {}
    for r in valid:
        if r.peptide_length <= 9:
            bucket = "8-9"
        elif r.peptide_length <= 11:
            bucket = "10-11"
        else:
            bucket = "12+"
        by_length.setdefault(bucket, []).append(r)

    summary["by_peptide_length"] = {
        bucket: {
            "n": len(rows),
            "mean_recall_at_5": sum(r.recall_at_k.get(5, 0.0) for r in rows) / len(rows),
        }
        for bucket, rows in sorted(by_length.items())
    }

    return summary


def results_to_dict(results: list[StructureEvaluation]) -> list[dict]:
    return [asdict(r) for r in results]
