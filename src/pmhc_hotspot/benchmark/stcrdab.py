"""Convert STCRDab summary exports into pmhc-hotspot benchmark manifests."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from pmhc_hotspot.features.allele_rules import normalize_allele

_AA_TOKEN = re.compile(r"[A-Za-z]{3}")
_AA_RUN = re.compile(r"[A-Za-z]{8,15}")
_HLA_ALLELE = re.compile(
    r"HLA[-\s]?([ABC])\s*\*?\s*(\d{2})\s*[:.]?\s*(\d{2})",
    re.IGNORECASE,
)
_HLA_ALLELE_COMPACT = re.compile(
    r"HLA[-\s]?([ABC])\s*\*?\s*(\d{4})",
    re.IGNORECASE,
)
_HLA_A2_STYLE = re.compile(
    r"HLA[-\s]?([ABC])\s*(\d{1,2})\s*\*?\s*(\d{2})",
    re.IGNORECASE,
)
_MER_LENGTH = re.compile(r"(\d{2})-?\s*mer", re.IGNORECASE)


def _clean(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text or text.upper() in {"NA", "NAN", "NONE"}:
        return None
    return text


def infer_allele(compound: str | None, antigen_name: str | None = None) -> str | None:
    """Best-effort HLA allele parse from STCRDab text fields."""
    text = " ".join(filter(None, [compound, antigen_name]))
    if not text:
        return None

    for pattern in (_HLA_ALLELE,):
        match = pattern.search(text)
        if match:
            return normalize_allele(f"HLA-{match.group(1).upper()}*{match.group(2)}:{match.group(3)}")

    match = _HLA_ALLELE_COMPACT.search(text)
    if match:
        digits = match.group(2)
        return normalize_allele(f"HLA-{match.group(1).upper()}*{digits[:2]}:{digits[2:]}")

    match = _HLA_A2_STYLE.search(text)
    if match:
        locus = match.group(1).upper()
        part1 = match.group(2).zfill(2)
        part2 = match.group(3)
        return normalize_allele(f"HLA-{locus}*{part1}:{part2}")

    return None


def estimate_peptide_length(antigen_name: str | None, compound: str | None = None) -> int | None:
    """Estimate peptide length from STCRDab antigen/compound text."""
    texts = [t for t in (antigen_name, compound) if t]
    for text in texts:
        mer = _MER_LENGTH.search(text)
        if mer:
            return int(mer.group(1))

    for text in texts:
        lowered = text.lower()
        if "peptide" in lowered or "epitope" in lowered:
            tokens = lowered.replace(",", " ").split()
            for token in tokens:
                if token.isalpha() and 8 <= len(token) <= 15:
                    return len(token)

    for text in texts:
        match = _AA_RUN.search(text.replace("-", ""))
        if match:
            return len(match.group(0))

    if antigen_name:
        triplets = _AA_TOKEN.findall(antigen_name)
        if 8 <= len(triplets) <= 15:
            return len(triplets)

    return None


def load_stcrdab_summary(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    return pd.read_csv(path, sep="\t", dtype=str)


def default_eval_pdb_ids() -> set[str]:
    from pmhc_hotspot.benchmark.manifest import BenchmarkManifest

    return {entry.pdb_id.upper() for entry in BenchmarkManifest.default()}


def convert_stcrdab_summary(
    path: str | Path,
    *,
    exclude_pdb_ids: set[str] | None = None,
    min_peptide_length: int = 8,
    max_peptide_length: int = 15,
    max_resolution: float | None = 3.5,
    engineered: str = "include",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Convert an STCRDab summary TSV into manifest rows.

    Returns (structures, report) where report summarizes filtering decisions.
    """
    df = load_stcrdab_summary(path)
    exclude_pdb_ids = {p.upper() for p in (exclude_pdb_ids or set())}
    if not exclude_pdb_ids:
        exclude_pdb_ids = default_eval_pdb_ids()

    report: dict[str, Any] = {
        "source": str(path),
        "input_rows": len(df),
        "excluded": [],
        "included": 0,
    }

    rows: list[dict[str, Any]] = []
    for _, raw in df.iterrows():
        pdb_id = _clean(raw.get("pdb"))
        if not pdb_id:
            continue
        pdb_id = pdb_id.upper()

        antigen_type = (_clean(raw.get("antigen_type")) or "").lower()
        mhc_type = (_clean(raw.get("mhc_type")) or "").upper()
        tcr_type = (_clean(raw.get("TCRtype")) or "").lower()
        if antigen_type != "peptide" or mhc_type != "MH1" or tcr_type != "abtcr":
            continue

        peptide_chain = _clean(raw.get("antigen_chain"))
        hla_chain = _clean(raw.get("mhc_chain1"))
        alpha_chain = _clean(raw.get("Achain"))
        beta_chain = _clean(raw.get("Bchain"))
        if not all([peptide_chain, hla_chain, alpha_chain, beta_chain]):
            report["excluded"].append({"pdb_id": pdb_id, "reason": "missing_chain_ids"})
            continue

        engineered_flag = (_clean(raw.get("engineered")) or "").lower() == "true"
        if engineered == "exclude" and engineered_flag:
            report["excluded"].append({"pdb_id": pdb_id, "reason": "engineered"})
            continue

        resolution = pd.to_numeric(raw.get("resolution"), errors="coerce")
        if max_resolution is not None and pd.notna(resolution) and float(resolution) > max_resolution:
            report["excluded"].append(
                {"pdb_id": pdb_id, "reason": f"resolution>{max_resolution}", "resolution": float(resolution)}
            )
            continue

        peptide_length = estimate_peptide_length(
            _clean(raw.get("antigen_name")),
            _clean(raw.get("compound")),
        )
        if peptide_length is not None and (
            peptide_length < min_peptide_length or peptide_length > max_peptide_length
        ):
            report["excluded"].append(
                {
                    "pdb_id": pdb_id,
                    "reason": "peptide_length_out_of_range",
                    "peptide_length": peptide_length,
                }
            )
            continue

        allele = infer_allele(_clean(raw.get("compound")), _clean(raw.get("antigen_name")))
        notes_parts = [
            _clean(raw.get("compound")) or "",
            _clean(raw.get("antigen_name")) or "",
        ]
        if engineered_flag:
            notes_parts.append("engineered=True")
        if peptide_length is not None:
            notes_parts.append(f"peptide_length~{peptide_length}")
        if pd.notna(resolution):
            notes_parts.append(f"resolution={float(resolution):.2f}A")

        rows.append(
            {
                "pdb_id": pdb_id,
                "allele": allele,
                "peptide_chain": peptide_chain,
                "hla_chain": hla_chain,
                "tcr_chains": [alpha_chain, beta_chain],
                "notes": "; ".join(p for p in notes_parts if p),
                "_resolution": float(resolution) if pd.notna(resolution) else 999.0,
            }
        )

    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        pdb_id = row["pdb_id"]
        if pdb_id in exclude_pdb_ids:
            report["excluded"].append({"pdb_id": pdb_id, "reason": "held_out_eval_manifest"})
            continue
        current = deduped.get(pdb_id)
        if current is None or row["_resolution"] < current["_resolution"]:
            deduped[pdb_id] = row

    structures = []
    for pdb_id in sorted(deduped):
        row = deduped[pdb_id]
        row.pop("_resolution", None)
        structures.append(row)

    report["included"] = len(structures)
    report["unique_pdbs"] = len(deduped)
    report["excluded_eval_overlap"] = sorted(exclude_pdb_ids & {r["pdb_id"] for r in rows})
    return structures, report


def write_training_manifest(
    structures: list[dict[str, Any]],
    output_path: str | Path,
    *,
    description: str = "STCRDab-derived TCR-pMHC training structures",
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "description": description,
        "structures": structures,
    }
    with output_path.open("w") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False, default_flow_style=False)
    return output_path
