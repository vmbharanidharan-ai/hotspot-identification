"""Convert residue predictions into ML-ready rows."""

from __future__ import annotations

import pandas as pd


def build_training_frame(
    prediction_result,
    labels_by_position: dict[str, int],
    *,
    pdb_id: str | None = None,
    allele: str | None = None,
    peptide_length: int | None = None,
    skip_low_confidence: bool = False,
) -> pd.DataFrame:
    rows = []
    for r in prediction_result.residue_scores:
        if skip_low_confidence and r.low_confidence:
            continue
        rows.append(
            {
                "pdb_id": pdb_id,
                "peptide": prediction_result.peptide_sequence,
                "allele": allele,
                "peptide_length": peptide_length or prediction_result.peptide_length,
                "position": r.position,
                "aa": r.aa,
                "sasa": r.relative_sasa,
                "protrusion": r.protrusion,
                "curvature": r.curvature,
                "bulge": r.bulge,
                "hla_contacts": r.hla_contacts,
                "peptide_contacts": r.peptide_contacts,
                "mutation_proximity": r.mutation_proximity,
                "confidence": r.confidence,
                "anchor_penalty": r.anchor_penalty,
                "chemical_score": r.chemical_score,
                "tcr_exposure_prior": r.tcr_exposure_prior,
                "buried": int(r.is_buried),
                "is_anchor": int(r.is_anchor),
                "label": int(labels_by_position.get(r.position, 0)),
            }
        )
    return pd.DataFrame(rows)
