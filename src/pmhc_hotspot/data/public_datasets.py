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

IEDB_PEPTIDE_COLUMNS = [
    "Epitope - Name",
    "epitope - name",
    "peptide_sequence",
    "peptide",
    "sequence",
    "Epitope Name",
]
IEDB_ALLELE_COLUMNS = [
    "MHC Restriction - Name",
    "mhc restriction - name",
    "mhc_allele",
    "allele",
    "hla_allele",
    "MHC Allele",
]
IEDB_LABEL_COLUMNS = [
    "Assay - Qualitative Measurement",
    "assay - qualitative measurement",
    "qualitative_measure",
    "binder",
    "label",
    "binder_class",
    "outcome",
]
IEDB_GROUP_COLUMNS = [
    "Reference - IEDB IRI",
    "Reference - PMID",
    "reference - iedb iri",
    "reference - pmid",
    "reference_id",
    "group_id",
    "Assay ID - IEDB IRI",
]
IEDB_ASSAY_COLUMNS = [
    "Assay - Method",
    "Assay - Response measured",
    "assay_type",
    "assay",
    "measurement_type",
]
IEDB_AFFINITY_COLUMNS = [
    "Assay - Quantitative measurement",
    "assay - quantitative measurement",
    "measurement_value",
    "affinity",
    "delta_g",
    "ic50",
    "IC50",
]
IEDB_PDB_COLUMNS = [
    "Assay - PDB ID",
    "assay - pdb id",
    "pdb_id",
    "structure_id",
    "PDB",
]
IEDB_OBJECT_TYPE_COLUMNS = ["Epitope - Object Type", "epitope - object type"]
IEDB_MHC_CLASS_COLUMNS = ["MHC Restriction - Class", "mhc restriction - class"]

ATLAS_PEPTIDE_COLUMNS = IEDB_PEPTIDE_COLUMNS + ["Peptide", "peptide_seq", "Peptide Sequence"]
ATLAS_ALLELE_COLUMNS = IEDB_ALLELE_COLUMNS + ["MHC", "MHC Allele"]
ATLAS_LABEL_COLUMNS = IEDB_LABEL_COLUMNS + ["Binder", "binder", "Binding"]
ATLAS_GROUP_COLUMNS = IEDB_GROUP_COLUMNS + ["complex_id", "ATLAS ID", "atlas_id"]
ATLAS_AFFINITY_COLUMNS = IEDB_AFFINITY_COLUMNS + ["Delta_G", "deltaG", "Affinity"]


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


def _read_table(path: str | Path) -> pd.DataFrame:
    """Read CSV or TSV (IEDB/ATLAS exports)."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in {".tsv", ".txt"}:
        return pd.read_csv(path, sep="\t", low_memory=False)
    return pd.read_csv(path, low_memory=False)


def _column_lookup(df: pd.DataFrame, names: list[str]) -> str | None:
    """Return actual dataframe column name matching one of `names`."""
    lower_map = {str(c).lower(): c for c in df.columns}
    for name in names:
        if name in df.columns:
            return name
        key = name.lower()
        if key in lower_map:
            return lower_map[key]
    return None


def _first_column(df: pd.DataFrame, names: list[str]) -> pd.Series | None:
    col = _column_lookup(df, names)
    return df[col] if col is not None else None


def _filter_iedb_rows(df: pd.DataFrame, mhc_class_i_only: bool) -> pd.DataFrame:
    """Keep linear peptides and optionally MHC class I rows."""
    out = df
    obj_col = _column_lookup(df, IEDB_OBJECT_TYPE_COLUMNS)
    if obj_col is not None:
        mask = df[obj_col].astype(str).str.lower().str.contains("linear", na=False)
        out = out.loc[mask]
    if mhc_class_i_only:
        class_col = _column_lookup(df, IEDB_MHC_CLASS_COLUMNS)
        if class_col is not None:
            mask = out[class_col].astype(str).str.strip().str.upper().isin({"I", "1"})
            out = out.loc[mask]
    return out


def _standardize_frame(
    df: pd.DataFrame,
    source: str,
    *,
    peptide_cols: list[str],
    allele_cols: list[str],
    label_cols: list[str],
    group_cols: list[str],
    assay_cols: list[str],
    affinity_cols: list[str],
    pdb_cols: list[str],
) -> pd.DataFrame:
    peptide = _first_column(df, peptide_cols)
    allele = _first_column(df, allele_cols)
    label_raw = _first_column(df, label_cols)
    group = _first_column(df, group_cols)
    assay = _first_column(df, assay_cols)
    affinity = _first_column(df, affinity_cols)
    pdb = _first_column(df, pdb_cols)

    if peptide is None:
        found = ", ".join(str(c) for c in list(df.columns)[:8])
        raise ValueError(
            f"{source}: missing peptide column. First columns: {found}..."
        )

    out = pd.DataFrame()
    out["peptide"] = peptide.astype(str).str.strip().str.upper()
    out["allele"] = allele
    out["label"] = label_raw.map(_normalize_label) if label_raw is not None else None
    if out["label"].isna().all() and affinity is not None:
        out["label"] = affinity.notna().astype(int)
    out["source"] = source
    out["group_id"] = group.astype(str) if group is not None else df.index.astype(str)
    out["assay_type"] = assay
    out["affinity"] = pd.to_numeric(affinity, errors="coerce") if affinity is not None else None
    if pdb is not None:
        pdb_clean = pdb.astype(str).str.strip().str.upper()
        out["pdb_id"] = pdb_clean.where(~pdb_clean.isin({"", "NAN", "NONE"}), None)
    else:
        out["pdb_id"] = None
    return out


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


def load_iedb_csv(path: str | Path, *, mhc_class_i_only: bool = True) -> pd.DataFrame:
    """Load an IEDB peptide-MHC export (CSV or TSV, native IEDB headers supported)."""
    df = _read_table(path)
    df = _filter_iedb_rows(df, mhc_class_i_only=mhc_class_i_only)
    standardized = _standardize_frame(
        df,
        "IEDB",
        peptide_cols=IEDB_PEPTIDE_COLUMNS,
        allele_cols=IEDB_ALLELE_COLUMNS,
        label_cols=IEDB_LABEL_COLUMNS,
        group_cols=IEDB_GROUP_COLUMNS,
        assay_cols=IEDB_ASSAY_COLUMNS,
        affinity_cols=IEDB_AFFINITY_COLUMNS,
        pdb_cols=IEDB_PDB_COLUMNS,
    )
    return _clean_public_frame(standardized)


def load_atlas_csv(path: str | Path) -> pd.DataFrame:
    """Load an ATLAS TCR-pMHC export (CSV or TSV)."""
    df = _read_table(path)
    standardized = _standardize_frame(
        df,
        "ATLAS",
        peptide_cols=ATLAS_PEPTIDE_COLUMNS,
        allele_cols=ATLAS_ALLELE_COLUMNS,
        label_cols=ATLAS_LABEL_COLUMNS,
        group_cols=ATLAS_GROUP_COLUMNS,
        assay_cols=IEDB_ASSAY_COLUMNS,
        affinity_cols=ATLAS_AFFINITY_COLUMNS,
        pdb_cols=IEDB_PDB_COLUMNS + ["Template PDB", "template_pdb"],
    )
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
