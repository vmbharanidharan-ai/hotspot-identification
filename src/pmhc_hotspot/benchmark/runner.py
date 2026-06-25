"""Benchmark runner for curated TCR-pMHC structures."""

from __future__ import annotations

import logging
from pathlib import Path

from pmhc_hotspot.benchmark.dataset import PDBDownloader, extract_peptide_contact_positions
from pmhc_hotspot.benchmark.evaluate import aggregate_results, evaluate_structure, results_to_dict
from pmhc_hotspot.benchmark.manifest import BenchmarkManifest

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
    ) -> dict:
        manifest = (
            BenchmarkManifest.default()
            if manifest_path is None
            else BenchmarkManifest(manifest_path)
        )
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
                predictor = self.predictor
                if allele != self.predictor.allele or entry.peptide_chain or entry.hla_chain:
                    from pmhc_hotspot.api import HotspotPredictor

                    predictor = HotspotPredictor(
                        allele=allele,
                        peptide_chain=entry.peptide_chain,
                        hla_chain=entry.hla_chain,
                        hotspot_config=self.predictor.hotspot_config,
                        weights=self.predictor.weights,
                    )

                prediction = predictor.predict(pdb_path)
                ordered = [r.position for r in prediction.residue_scores]
                structure = predictor._load_structure_for_benchmark(pdb_path)
                contacts = extract_peptide_contact_positions(structure, entry)

                ev = evaluate_structure(
                    pdb_id=entry.pdb_id,
                    predicted_ordered=ordered,
                    truth_positions=contacts,
                    allele=allele,
                    peptide_length=prediction.peptide_length,
                    top_k=top_k,
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
            "summary": aggregate_results(results),
            "results": results_to_dict(results),
        }
