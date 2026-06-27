"""Export prediction results to TSV, JSON, and RFdiffusion templates."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

from pmhc_hotspot.types import PredictionResult


def to_tsv(result: PredictionResult, path: str | Path) -> None:
    rows = []
    for r in result.residue_scores:
        row = r.to_dict()
        row["explanation"] = json.dumps(r.explanation)
        row["rfdiffusion_token"] = r.rfdiffusion_token
        row["selected_hotspot"] = r.rfdiffusion_token in result.rfdiffusion_hotspot_res
        rows.append(row)
    pd.DataFrame(rows).to_csv(path, sep="\t", index=False)


def to_json(result: PredictionResult, path: str | Path) -> None:
    with open(path, "w") as fh:
        json.dump(result.to_dict(), fh, indent=2)


def export_hotspot_yaml(result: PredictionResult, path: str | Path, **kwargs) -> Path:
    """Re-export standardized hotspot YAML v1.0 (see hotspot_export module)."""
    from pmhc_hotspot.hotspot_export import export_hotspot_yaml as _export

    return _export(result, output_file=path, **kwargs)


def build_contig_template(
    peptide_chain_id: str,
    peptide_resseqs: list[int],
    hla_chain_id: str,
    hla_resseqs: list[int],
    binder_length_min: int = 50,
    binder_length_max: int = 80,
) -> str:
    """
    RFdiffusion contig string fixing peptide + HLA target chains.

    Example: ``P1-9/0 H25-180/0 50-80``
    """
    if not peptide_resseqs or not hla_resseqs:
        return ""
    pep_span = f"{peptide_chain_id}{peptide_resseqs[0]}-{peptide_resseqs[-1]}"
    hla_span = f"{hla_chain_id}{hla_resseqs[0]}-{hla_resseqs[-1]}"
    if binder_length_min == binder_length_max:
        binder_span = f"{binder_length_min}-{binder_length_max}"
    else:
        binder_span = f"{binder_length_min}-{binder_length_max}"
    return f"{pep_span}/0 {hla_span}/0 {binder_span}"


def export_rfdiffusion_template(
    result: PredictionResult,
    path: str | Path,
    *,
    binder_length_min: int = 50,
    binder_length_max: int = 80,
    num_designs: int = 100,
) -> None:
    """
    Export a minimal RFdiffusion config template.

    This is a helper template — verify against your RFdiffusion version.
    Does not claim full ownership of RFdiffusion internals.
    """
    template = {
        "version_note": "Verify against your RFdiffusion release; template for pmhc-hotspot v0.1.0",
        "ppi": {
            "hotspot_res": result.rfdiffusion_hotspot_res,
            "target_chains": result.hla_chain_ids,
        },
        "contigmap": {
            "contigs": result.contig_template,
            "num_designs": num_designs,
            "binder_length_min": binder_length_min,
            "binder_length_max": binder_length_max,
        },
        "peptide_chain": result.peptide_chain_id,
        "allele": result.allele,
        "hotspot_positions": [r.position for r in result.hotspots],
        "patches": [p.to_dict() for p in result.patches],
    }
    with open(path, "w") as fh:
        yaml.safe_dump(template, fh, sort_keys=False)
