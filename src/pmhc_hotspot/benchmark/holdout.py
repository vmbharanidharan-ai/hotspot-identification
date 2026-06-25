"""Leave-structures-out validation for structural ML models."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pmhc_hotspot.benchmark.dataset import (
    PDBDownloader,
    extract_peptide_contact_positions,
    resolve_benchmark_entry,
)
from pmhc_hotspot.benchmark.evaluate import (
    StructureEvaluation,
    aggregate_results,
    evaluate_structure,
    results_to_dict,
)
from pmhc_hotspot.benchmark.manifest import BenchmarkManifest
from pmhc_hotspot.ml.inference import order_positions_by_score
from pmhc_hotspot.ml.persistence import StagedModelBundle, save_staged_bundle
from pmhc_hotspot.ml.staged import run_staged_training


def run_leave_structures_out(
    public_df: pd.DataFrame,
    structural_df: pd.DataFrame,
    held_out_pdb_ids: list[str],
    *,
    manifest_path: str | None = None,
    model_type: str = "xgboost",
    contact_mode: str = "standard",
    scoring_mode: str = "hybrid",
    save_model_path: str | None = None,
    download: bool = False,
    cache_dir: str = "data/pdb",
    use_pretrain: bool = True,
) -> dict:
    """Train on all structures except held-out PDBs, then benchmark held-out only."""
    held_out = {p.upper() for p in held_out_pdb_ids}
    train_df = structural_df[~structural_df["pdb_id"].astype(str).str.upper().isin(held_out)].copy()
    if train_df.empty:
        raise ValueError("No training rows remain after holdout split")
    if train_df["label"].nunique() < 2:
        raise ValueError("Training split needs both positive and negative residue labels")

    staged = run_staged_training(
        public_df,
        train_df,
        model_type=model_type,
        contact_mode=contact_mode,
        use_pretrain=use_pretrain,
    )
    bundle: StagedModelBundle = staged["model_bundle"]

    if save_model_path:
        save_staged_bundle(save_model_path, bundle)

    manifest = BenchmarkManifest.resolve(manifest_path)
    entries = [e for e in manifest if e.pdb_id.upper() in held_out]
    if download:
        entries = PDBDownloader(cache_dir).ensure_manifest_paths(entries)

    from pmhc_hotspot.api import HotspotPredictor

    base_predictor = HotspotPredictor()
    evaluations: list[StructureEvaluation] = []
    for entry in entries:
        pdb_path = entry.resolved_pdb_path
        if not Path(pdb_path).exists():
            evaluations.append(
                StructureEvaluation(
                    pdb_id=entry.pdb_id,
                    allele=entry.allele,
                    peptide_length=0,
                    n_truth_contacts=0,
                    skipped=True,
                    error=f"PDB not found: {pdb_path}",
                )
            )
            continue
        try:
            structure = base_predictor._load_structure_for_benchmark(pdb_path)
            entry = resolve_benchmark_entry(structure, entry)
            predictor = HotspotPredictor(
                allele=entry.allele,
                peptide_chain=entry.peptide_chain,
                hla_chain=entry.hla_chain,
                ml_bundle=bundle,
                scoring_mode=scoring_mode,
            )
            prediction = predictor.predict(pdb_path, select_hotspots=False)
            ordered = order_positions_by_score(
                prediction,
                scoring_mode=scoring_mode,
                bundle=bundle,
                hybrid_alpha=bundle.hybrid_alpha,
            )
            contacts = extract_peptide_contact_positions(
                structure, entry, contact_mode=contact_mode
            )
            buried_anchors = {
                r.position for r in prediction.residue_scores if r.is_anchor and r.is_buried
            }
            evaluations.append(
                evaluate_structure(
                    pdb_id=entry.pdb_id,
                    predicted_ordered=ordered,
                    truth_positions=contacts,
                    allele=entry.allele,
                    peptide_length=prediction.peptide_length,
                    buried_anchor_positions=buried_anchors,
                )
            )
        except Exception as exc:
            evaluations.append(
                StructureEvaluation(
                    pdb_id=entry.pdb_id,
                    allele=entry.allele,
                    peptide_length=0,
                    n_truth_contacts=0,
                    skipped=True,
                    error=str(exc),
                )
            )

    return {
        "held_out": sorted(held_out),
        "scoring_mode": scoring_mode,
        "contact_mode": contact_mode,
        "train_rows": len(train_df),
        "pretrain_cv": staged["pretrain_cv"],
        "finetune_cv_train_split": staged["finetune_cv"],
        "held_out_benchmark": {
            "summary": aggregate_results(evaluations),
            "results": results_to_dict(evaluations),
        },
    }
