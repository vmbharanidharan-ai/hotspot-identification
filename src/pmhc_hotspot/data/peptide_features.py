"""Sequence-level features for public pretraining (no structure required)."""

from __future__ import annotations

import pandas as pd

from pmhc_hotspot.constants import HYDROPHOBIC_FOR_INTERFACE, RESIDUE_CHEMICAL_SCORE
from pmhc_hotspot.features.allele_rules import normalize_allele

AROMATIC = frozenset("FWY")
POSITIVE = frozenset("KR")
NEGATIVE = frozenset("DE")


def peptide_biochemical_features(peptide: str) -> dict[str, float]:
    seq = peptide.upper()
    n = len(seq) or 1
    chem = [RESIDUE_CHEMICAL_SCORE.get(aa, 0.0) for aa in seq]
    return {
        "peptide_length": float(n),
        "hydrophobic_frac": sum(aa in HYDROPHOBIC_FOR_INTERFACE for aa in seq) / n,
        "aromatic_frac": sum(aa in AROMATIC for aa in seq) / n,
        "positive_frac": sum(aa in POSITIVE for aa in seq) / n,
        "negative_frac": sum(aa in NEGATIVE for aa in seq) / n,
        "mean_chemical_score": sum(chem) / n,
        "max_chemical_score": max(chem) if chem else 0.0,
    }


def featurize_peptide_table(df: pd.DataFrame) -> pd.DataFrame:
    """Add biochemical sequence features and normalized allele to a public dataset."""
    out = df.copy()
    out["allele"] = out["allele"].map(lambda x: normalize_allele(x) if pd.notna(x) else None)
    if "peptide_length" in out.columns:
        out = out.drop(columns=["peptide_length"])
    feat_rows = [peptide_biochemical_features(p) for p in out["peptide"]]
    feat_df = pd.DataFrame(feat_rows, index=out.index)
    return pd.concat([out, feat_df], axis=1)
