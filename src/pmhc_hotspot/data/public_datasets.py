"""Load and normalize IEDB/ATLAS-style public training records."""

from __future__ import annotations

import re
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

ATLAS_PEPTIDE_COLUMNS = IEDB_PEPTIDE_COLUMNS + [
    "PEPseq",
    "pepseq",
    "Peptide",
    "peptide_seq",
    "Peptide Sequence",
]
ATLAS_ALLELE_COLUMNS = IEDB_ALLELE_COLUMNS + [
    "MHCname",
    "mhcname",
    "MHCname_PDB",
    "MHC",
    "MHC Allele",
]
ATLAS_LABEL_COLUMNS = IEDB_LABEL_COLUMNS + ["Binder", "binder", "Binding"]
ATLAS_GROUP_COLUMNS = IEDB_GROUP_COLUMNS + ["PMID", "pmid", "complex_id", "ATLAS ID", "atlas_id"]
ATLAS_DELTA_G_COLUMNS = [
    "DeltaG_kcal_per_mol",
    "deltag_kcal_per_mol",
    "Delta_G",
    "deltaG",
]
ATLAS_KD_COLUMNS = ["Kd_microM", "kd_microm", "Kd", "kd"]
ATLAS_AFFINITY_COLUMNS = IEDB_AFFINITY_COLUMNS + ATLAS_DELTA_G_COLUMNS + ATLAS_KD_COLUMNS + ["Affinity"]
ATLAS_PDB_COLUMNS = IEDB_PDB_COLUMNS + ["true_PDB", "template_PDB", "Template PDB", "template_pdb"]
ATLAS_ASSAY_COLUMNS = IEDB_ASSAY_COLUMNS + ["Exp. Method", "Structure_Method", "Exp Method"]
ATLAS_PEP_MUT_COLUMNS = ["PEP_mut", "pep_mut"]
ATLAS_TCR_MUT_COLUMNS = ["TCR_mut", "tcr_mut"]

# ATLAS reports TCR-pMHC affinity; thresholds approximate strong vs weak engagement.
ATLAS_DELTA_G_BIND_MAX = -6.0  # kcal/mol; more negative = stronger binding
ATLAS_KD_BIND_MAX_UM = 25.0  # µM


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
    na_values = ["\\N", "N/A", "NA", ""]
    if suffix in {".tsv", ".txt"}:
        return pd.read_csv(path, sep="\t", low_memory=False, na_values=na_values)
    return pd.read_csv(path, low_memory=False, na_values=na_values)


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


def _parse_atlas_measurement(value) -> float | None:
    """Parse ATLAS affinity strings such as '12.5 +/- 2.1' or '>200'."""
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text.upper() in {"\\N", "N/A", "NA", "NAN", "NONE", ""}:
        return None
    if text.startswith(">"):
        match = re.search(r"([0-9.]+)", text[1:])
        return float(match.group(1)) if match else None
    if text.startswith("<"):
        match = re.search(r"([0-9.]+)", text[1:])
        return float(match.group(1)) if match else None
    match = re.match(r"^([0-9.]+)", text)
    return float(match.group(1)) if match else None


def _parse_measurement_series(series: pd.Series) -> pd.Series:
    return series.map(_parse_atlas_measurement)


def _derive_atlas_labels(delta_g: pd.Series, kd_um: pd.Series) -> pd.Series:
    """Binary label from ATLAS affinity: 1 = strong, 0 = weak/non-binder."""
    labels = []
    for dg, kd in zip(delta_g, kd_um):
        if pd.notna(dg):
            labels.append(1 if dg <= ATLAS_DELTA_G_BIND_MAX else 0)
        elif pd.notna(kd):
            labels.append(1 if kd <= ATLAS_KD_BIND_MAX_UM else 0)
        else:
            labels.append(None)
    return pd.Series(labels, dtype="object")


def _filter_atlas_rows(df: pd.DataFrame, *, wt_only: bool) -> pd.DataFrame:
    """Keep wild-type peptide rows (and optionally wild-type TCR) for peptide-level pretrain."""
    out = df
    pep_mut_col = _column_lookup(df, ATLAS_PEP_MUT_COLUMNS)
    if pep_mut_col is not None:
        out = out.loc[out[pep_mut_col].astype(str).str.upper().eq("WT")]
    if wt_only:
        tcr_mut_col = _column_lookup(df, ATLAS_TCR_MUT_COLUMNS)
        if tcr_mut_col is not None:
            out = out.loc[out[tcr_mut_col].astype(str).str.upper().eq("WT")]
    return out


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


def load_atlas_csv(path: str | Path, *, wt_only: bool = True) -> pd.DataFrame:
    """Load an ATLAS TCR-pMHC export (CSV or TSV, native ATLAS headers supported)."""
    df = _read_table(path)
    df = _filter_atlas_rows(df, wt_only=wt_only)
    standardized = _standardize_frame(
        df,
        "ATLAS",
        peptide_cols=ATLAS_PEPTIDE_COLUMNS,
        allele_cols=ATLAS_ALLELE_COLUMNS,
        label_cols=ATLAS_LABEL_COLUMNS,
        group_cols=ATLAS_GROUP_COLUMNS,
        assay_cols=ATLAS_ASSAY_COLUMNS,
        affinity_cols=ATLAS_AFFINITY_COLUMNS,
        pdb_cols=ATLAS_PDB_COLUMNS,
    )
    delta_g_col = _first_column(df, ATLAS_DELTA_G_COLUMNS)
    kd_col = _first_column(df, ATLAS_KD_COLUMNS)
    delta_g = _parse_measurement_series(delta_g_col) if delta_g_col is not None else pd.Series(
        [None] * len(standardized), index=standardized.index
    )
    kd_um = _parse_measurement_series(kd_col) if kd_col is not None else pd.Series(
        [None] * len(standardized), index=standardized.index
    )
    if standardized["label"].isna().all():
        standardized["label"] = _derive_atlas_labels(delta_g, kd_um)
    if standardized["affinity"].isna().all():
        standardized["affinity"] = delta_g.where(delta_g.notna(), kd_um)
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
