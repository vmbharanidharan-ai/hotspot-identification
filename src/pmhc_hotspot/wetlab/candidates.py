"""Wet-lab candidate selection (Phase 5.1)."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import List

from pmhc_hotspot.api import HotspotPredictor
from pmhc_hotspot.design.af2_scorer import AF2InterfaceScorer
from pmhc_hotspot.design.rfdiffusion_orchestrator import RFdiffusionDesigner
from pmhc_hotspot.uncertainty.confidence import ConfidenceEstimator


def select_candidates_for_wetlab(
    eval_structures: List[dict],
    *,
    n_candidates: int = 20,
    scoring_mode: str = "hybrid",
    output_csv: Path = Path("results/wetlab_candidates.csv"),
) -> Path:
    confidence = ConfidenceEstimator()
    scorer = AF2InterfaceScorer()
    _designer = RFdiffusionDesigner(num_designs=3)

    rows: list[dict] = []
    for entry in eval_structures:
        pdb_path = Path(entry["pdb_path"])
        entry_predictor = HotspotPredictor(
            allele=entry.get("allele"),
            scoring_mode=scoring_mode,
            peptide_chain=entry.get("peptide_chain"),
            hla_chain=entry.get("hla_chain"),
        )
        result = entry_predictor.predict(pdb_path)
        confs = confidence.estimate_for_result(result)
        hotspots = ",".join(h.position for h in result.hotspots)
        af2 = scorer.score_interface(pdb_path, pdb_path)
        mean_conf = confs[0].confidence_level if confs else "medium"
        rows.append(
            {
                "pdb_id": entry.get("pdb_id", pdb_path.stem),
                "peptide_seq": result.peptide_sequence,
                "designed_seq": "TBD",
                "predicted_hotspots": hotspots,
                "confidence": mean_conf,
                "af2_pae": af2.get("af2_ipae", af2.get("interface_pae")),
                "interface_contacts": af2.get("contact_count"),
                "notes": "GNN+RFdiffusion pipeline candidate",
            }
        )
        if len(rows) >= n_candidates:
            break

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="") as fh:
        fieldnames = list(rows[0].keys()) if rows else [
            "pdb_id",
            "peptide_seq",
            "designed_seq",
            "predicted_hotspots",
            "confidence",
            "af2_pae",
            "interface_contacts",
            "notes",
        ]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if rows:
            writer.writeheader()
            writer.writerows(rows)
    return output_csv
