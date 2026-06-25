"""Sequence-level features for public pretraining (no structure required)."""

from __future__ import annotations

import pandas as pd

from pmhc_hotspot.constants import HYDROPHOBIC_FOR_INTERFACE, RESIDUE_CHEMICAL_SCORE
from pmhc_hotspot.features.allele_rules import normalize_allele

AROMATIC = frozenset("FWY")
POSITIVE = frozenset("KR")
NEGATIVE = frozenset("DE")

MAX_PEPTIDE_POSITIONS = 15
PAD_AA = "PAD"
POSITION_NUMERIC_SUFFIXES = ("chem", "hydrophobic", "aromatic", "positive", "negative")

POSITION_FEATURE_COLUMNS = [
    f"pos_{i}_{suffix}"
    for i in range(1, MAX_PEPTIDE_POSITIONS + 1)
    for suffix in POSITION_NUMERIC_SUFFIXES
] + ["anchor_p2_chem", "anchor_omega_chem"]

POSITION_CATEGORICAL_COLUMNS = [f"pos_{i}_aa" for i in range(1, MAX_PEPTIDE_POSITIONS + 1)] + [
    "anchor_p2_aa",
    "anchor_omega_aa",
]


def _aa_numeric_properties(aa: str) -> dict[str, float]:
    return {
        "chem": RESIDUE_CHEMICAL_SCORE.get(aa, 0.0),
        "hydrophobic": float(aa in HYDROPHOBIC_FOR_INTERFACE),
        "aromatic": float(aa in AROMATIC),
        "positive": float(aa in POSITIVE),
        "negative": float(aa in NEGATIVE),
    }


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


def peptide_position_features(peptide: str, max_len: int = MAX_PEPTIDE_POSITIONS) -> dict:
    """Per-position biochemical features padded to `max_len` for variable-length peptides."""
    seq = peptide.upper()
    feats: dict[str, float | str] = {}

    for i in range(1, max_len + 1):
        prefix = f"pos_{i}"
        if i <= len(seq):
            aa = seq[i - 1]
            props = _aa_numeric_properties(aa)
            for suffix, value in props.items():
                feats[f"{prefix}_{suffix}"] = value
            feats[f"{prefix}_aa"] = aa
        else:
            for suffix in POSITION_NUMERIC_SUFFIXES:
                feats[f"{prefix}_{suffix}"] = 0.0
            feats[f"{prefix}_aa"] = PAD_AA

    if len(seq) >= 2:
        feats["anchor_p2_aa"] = seq[1]
        feats["anchor_p2_chem"] = RESIDUE_CHEMICAL_SCORE.get(seq[1], 0.0)
    else:
        feats["anchor_p2_aa"] = PAD_AA
        feats["anchor_p2_chem"] = 0.0

    if len(seq) >= 8:
        feats["anchor_omega_aa"] = seq[-1]
        feats["anchor_omega_chem"] = RESIDUE_CHEMICAL_SCORE.get(seq[-1], 0.0)
    else:
        feats["anchor_omega_aa"] = PAD_AA
        feats["anchor_omega_chem"] = 0.0

    return feats


def featurize_peptide_table(df: pd.DataFrame) -> pd.DataFrame:
    """Add global, position-specific, and allele-normalized features."""
    out = df.copy()
    out["allele"] = out["allele"].map(lambda x: normalize_allele(x) if pd.notna(x) else None)
    if "peptide_length" in out.columns:
        out = out.drop(columns=["peptide_length"])

    global_rows = [peptide_biochemical_features(p) for p in out["peptide"]]
    position_rows = [peptide_position_features(p) for p in out["peptide"]]
    feat_df = pd.concat(
        [pd.DataFrame(global_rows, index=out.index), pd.DataFrame(position_rows, index=out.index)],
        axis=1,
    )
    return pd.concat([out, feat_df], axis=1)
