"""Load and normalize IEDB/ATLAS-style public training records."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from pmhc_hotspot.data.validation import validate_peptide_sequence

STANDARD_COLUMNS = [
    "peptide",
    "allele",
    "label",
    "source",
    "group_id",
    "assay_type",
    "affinity",
    "pdb_id",
    "peptide_length",
]

POSITIVE_LABELS = {"positive", "binder", "yes", "1", "true"}
NEGATIVE_LABELS = {"negative", "non-binder", "no", "0", "false"}


@dataclass(frozen=True)
class PublicDatasetRecord:
    peptide: str
    allele: str | None
    label: int
    source: str
    group_id: str
    assay_type: str | None = None
    affinity: float | None = None
    pdb_id: str | None = None


def _normalize_label(value) -> int | None:
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)) and value in (0, 1):
        return int(value)
    text = str(value).strip().lower()
    if text in POSITIVE_LABELS:
        return 1
    if text in NEGATIVE_LABELS:
        return 0
    return None


def _first_column(df: pd.DataFrame, names: list[str]) -> pd.Series | None:
    for name in names:
        if name in df.columns:
            return df[name]
    return None


def _standardize_frame(df: pd.DataFrame, source: str) -> pd.DataFrame:
    peptide = _first_column(df, ["peptide_sequence", "peptide", "sequence"])
    allele = _first_column(df, ["mhc_allele", "allele", "hla_allele"])
    label_raw = _first_column(
        df,
        ["qualitative_measure", "binder", "label", "binder_class", "outcome"],
    )
    group = _first_column(df, ["reference_id", "group_id", "pdb_id", "complex_id"])
    assay = _first_column(df, ["assay_type", "assay", "measurement_type"])
    affinity = _first_column(df, ["measurement_value", "affinity", "delta_g", "ic50"])
    pdb = _first_column(df, ["pdb_id", "structure_id"])

    if peptide is None:
        raise ValueError(f"{source}: missing peptide column")

    out = pd.DataFrame()
    out["peptide"] = peptide.astype(str).str.strip().str.upper()
    out["allele"] = allele
    out["label"] = label_raw.map(_normalize_label) if label_raw is not None else None
    if out["label"].isna().all() and affinity is not None:
        out["label"] = affinity.notna().astype(int)
    out["source"] = source
    out["group_id"] = (
        group.astype(str) if group is not None else df.index.astype(str)
    )
    out["assay_type"] = assay
    out["affinity"] = pd.to_numeric(affinity, errors="coerce") if affinity is not None else None
    out["pdb_id"] = pdb.astype(str).str.upper().str.strip() if pdb is not None else None
    return out


def _clean_public_frame(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        try:
            peptide = validate_peptide_sequence(row["peptide"])
        except ValueError:
            continue
        label = row["label"]
        if pd.isna(label):
            continue
        rows.append({**row.to_dict(), "peptide": peptide, "label": int(label)})
    if not rows:
        return pd.DataFrame(columns=STANDARD_COLUMNS)
    out = pd.DataFrame(rows)
    out["peptide_length"] = out["peptide"].str.len()
    out["group_id"] = out["group_id"].astype(str)
    return out[STANDARD_COLUMNS]


def load_iedb_csv(path: str | Path) -> pd.DataFrame:
    """Load an IEDB-style peptide-MHC binding export (user-provided CSV)."""
    df = pd.read_csv(path)
    standardized = _standardize_frame(df, "IEDB")
    return _clean_public_frame(standardized)


def load_atlas_csv(path: str | Path) -> pd.DataFrame:
    """Load an ATLAS-style TCR-pMHC affinity export (user-provided CSV)."""
    df = pd.read_csv(path)
    standardized = _standardize_frame(df, "ATLAS")
    return _clean_public_frame(standardized)


def combine_public_datasets(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Merge normalized public datasets, keeping provenance."""
    valid = [f for f in frames if f is not None and not f.empty]
    if not valid:
        return pd.DataFrame(columns=STANDARD_COLUMNS)
    combined = pd.concat(valid, ignore_index=True)
    combined = combined.drop_duplicates(
        subset=["peptide", "allele", "source", "group_id", "label"],
        keep="first",
    )
    return combined.reset_index(drop=True)
