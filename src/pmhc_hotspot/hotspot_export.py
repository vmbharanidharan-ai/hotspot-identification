"""Standard hotspot YAML export/import (Phase 0.4)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from pmhc_hotspot.types import PredictionResult, ResidueScore
from pmhc_hotspot.uncertainty.confidence import ResidueConfidence


def _confidence_level(residue: ResidueScore, confidences: Optional[Dict[str, ResidueConfidence]]) -> str:
    if confidences and residue.position in confidences:
        return confidences[residue.position].confidence_level
    if residue.score >= 0.75:
        return "high"
    if residue.score <= 0.45:
        return "low"
    return "medium"


def export_hotspot_yaml(
    result: PredictionResult,
    *,
    pdb_id: str,
    peptide_seq: str,
    allele: Optional[str],
    tcr_chains: List[str],
    output_file: str | Path,
    model_version: str = "pmhc-hotspot",
    contact_entropy: Optional[Dict[int, float]] = None,
    confidences: Optional[List[ResidueConfidence]] = None,
) -> Path:
    """Serialize predictions to standardized hotspot YAML v1.0."""
    out = Path(output_file)
    conf_map = {c.position: c for c in (confidences or [])}
    patch_by_residue: dict[int, str] = {}
    for patch in result.patches:
        label = chr(ord("A") + patch.patch_id - 1) if patch.patch_id else "A"
        for r in patch.residues:
            patch_by_residue[r.resseq] = label

    hotspots_payload = []
    for h in result.hotspots:
        conf = conf_map.get(h.position)
        hotspots_payload.append(
            {
                "residue_index": h.position_index + 1,
                "one_letter_code": h.aa,
                "score": round(h.score, 4),
                "confidence": _confidence_level(h, conf_map),
                "tcr_contact_probability": round(
                    conf.calibrated_probability if conf else h.score, 4
                ),
                "contact_count": h.peptide_contacts,
                "patch_id": patch_by_residue.get(h.resseq),
            }
        )

    patches_payload = []
    for rank, patch in enumerate(result.patches, start=1):
        indices = [r.position_index + 1 for r in patch.residues]
        center = patch.residues[len(patch.residues) // 2].position_index + 1
        patches_payload.append(
            {
                "patch_id": chr(ord("A") + patch.patch_id - 1) if patch.patch_id else "A",
                "residue_indices": indices,
                "center_residue": center,
                "contiguity_score": round(patch.patch_score, 4),
                "geometric_center": [0.0, 0.0, 0.0],
                "importance_rank": rank,
            }
        )

    entropy_rows = []
    if contact_entropy:
        for idx, ent in sorted(contact_entropy.items()):
            entropy_rows.append({"index": idx + 1, "entropy": round(ent, 4)})

    payload = {
        "metadata": {
            "pdb_id": pdb_id,
            "allele": allele,
            "peptide_sequence": peptide_seq,
            "peptide_chain": result.peptide_chain_id,
            "mhc_chain": result.hla_chain_ids[0] if result.hla_chain_ids else None,
            "tcr_chains": list(tcr_chains),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_version": model_version,
            "tool": result.metadata.get("method", "pmhc-hotspot"),
        },
        "hotspots": hotspots_payload,
        "patches": patches_payload,
        "contacts": {"contact_entropy_per_residue": entropy_rows},
    }
    _validate_hotspot_payload(payload)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False)
    return out


def import_hotspot_yaml(yaml_file: str | Path) -> Dict[str, Any]:
    with Path(yaml_file).open() as fh:
        data = yaml.safe_load(fh) or {}
    _validate_hotspot_payload(data)
    return data


def _validate_hotspot_payload(data: Dict[str, Any]) -> None:
    required_meta = {"pdb_id", "peptide_sequence", "peptide_chain"}
    meta = data.get("metadata") or {}
    missing = required_meta - set(meta)
    if missing:
        raise ValueError(f"hotspot YAML missing metadata fields: {sorted(missing)}")
    if "hotspots" not in data:
        raise ValueError("hotspot YAML missing hotspots section")
