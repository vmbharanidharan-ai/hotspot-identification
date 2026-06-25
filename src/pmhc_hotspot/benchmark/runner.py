"""Benchmark runner for curated TCR-pMHC structures."""

from __future__ import annotations

import logging
from pathlib import Path

from pmhc_hotspot.benchmark.dataset import (
    PDBDownloader,
    extract_peptide_contact_positions,
    resolve_benchmark_entry,
)
from pmhc_hotspot.benchmark.contact_labels import ContactMode, describe_contact_mode
from pmhc_hotspot.benchmark.evaluate import aggregate_results, evaluate_structure, results_to_dict
from pmhc_hotspot.benchmark.manifest import BenchmarkManifest
from pmhc_hotspot.ml.inference import order_positions_by_score
from pmhc_hotspot.ml.persistence import StagedModelBundle, load_staged_bundle

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """Run hotspot predictor over a manifest and aggregate metrics."""

    def __init__(self, predictor):
        self.predictor = predictor

    def run_manifest(
        self,
        manifest_path: str | Path | None = None,
        *,
        top_k: tuple[int, ...] = (1, 3, 5),
        download: bool = False,
        cache_dir: str | Path = "data/pdb",
        contact_mode: ContactMode = "standard",
        scoring_mode: str = "deterministic",
        ml_bundle: StagedModelBundle | str | Path | None = None,
    ) -> dict:
        manifest = (
            BenchmarkManifest.default()
            if manifest_path is None
            else BenchmarkManifest(manifest_path)
        )
        if isinstance(ml_bundle, (str, Path)):
            ml_bundle = load_staged_bundle(ml_bundle)
        elif ml_bundle is None:
            ml_bundle = getattr(self.predictor, "ml_bundle", None)

        entries = list(manifest)
        if download:
            entries = PDBDownloader(cache_dir).ensure_manifest_paths(entries)

        results = []
        for entry in entries:
            pdb_path = entry.resolved_pdb_path
            if not Path(pdb_path).exists():
                logger.warning("Skipping %s: file not found (%s)", entry.pdb_id, pdb_path)
                from pmhc_hotspot.benchmark.evaluate import StructureEvaluation

                results.append(
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

            logger.info("Benchmarking %s", entry.pdb_id)
            try:
                allele = entry.allele or self.predictor.allele
                structure = self.predictor._load_structure_for_benchmark(pdb_path)
                entry = resolve_benchmark_entry(structure, entry)
                predictor = self.predictor
                if (
                    allele != self.predictor.allele
                    or entry.peptide_chain
                    or entry.hla_chain
                    or scoring_mode != getattr(self.predictor, "scoring_mode", "deterministic")
                    or ml_bundle is not getattr(self.predictor, "ml_bundle", None)
                ):
                    from pmhc_hotspot.api import HotspotPredictor

                    predictor = HotspotPredictor(
                        allele=allele,
                        peptide_chain=entry.peptide_chain,
                        hla_chain=entry.hla_chain,
                        hotspot_config=self.predictor.hotspot_config,
                        weights=self.predictor.weights,
                        ml_bundle=ml_bundle,
                        scoring_mode=scoring_mode,
                    )

                prediction = predictor.predict(pdb_path, select_hotspots=False)
                ordered = order_positions_by_score(
                    prediction,
                    scoring_mode=scoring_mode,
                    bundle=ml_bundle,
                    hybrid_alpha=ml_bundle.hybrid_alpha if ml_bundle else 0.6,
                )
                contacts = extract_peptide_contact_positions(structure, entry, contact_mode=contact_mode)
                buried_anchors = {
                    r.position for r in prediction.residue_scores if r.is_anchor and r.is_buried
                }

                ev = evaluate_structure(
                    pdb_id=entry.pdb_id,
                    predicted_ordered=ordered,
                    truth_positions=contacts,
                    allele=allele,
                    peptide_length=prediction.peptide_length,
                    top_k=top_k,
                    buried_anchor_positions=buried_anchors,
                )
                results.append(ev)
            except Exception as exc:
                logger.exception("Failed benchmarking %s", entry.pdb_id)
                from pmhc_hotspot.benchmark.evaluate import StructureEvaluation

                results.append(
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
            "manifest": str(manifest.path),
            "contact_mode": contact_mode,
            "contact_mode_description": describe_contact_mode(contact_mode),
            "scoring_mode": scoring_mode,
            "ml_bundle_loaded": ml_bundle is not None,
            "summary": aggregate_results(results),
            "results": results_to_dict(results),
        }
