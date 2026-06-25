"""Build ML training frames from benchmark outputs."""

from __future__ import annotations

import logging

from pmhc_hotspot.api import HotspotPredictor
from pmhc_hotspot.benchmark.dataset import PDBDownloader, extract_peptide_contact_positions, resolve_benchmark_entry
from pmhc_hotspot.benchmark.manifest import BenchmarkManifest
from pmhc_hotspot.ml.feature_matrix import build_training_frame

logger = logging.getLogger(__name__)


def build_training_dataset(
    manifest_path: str | None = None,
    *,
    download: bool = True,
    cache_dir: str = "data/pdb",
    contact_mode: str = "standard",
) -> "pd.DataFrame":
    """Aggregate residue-level training rows from a benchmark manifest."""
    import pandas as pd

    manifest = BenchmarkManifest.resolve(manifest_path)
    entries = list(manifest)
    if download:
        entries = PDBDownloader(cache_dir).ensure_manifest_paths(entries)

    frames = []
    for entry in entries:
        try:
            structure = HotspotPredictor()._load_structure_for_benchmark(entry.resolved_pdb_path)
            entry = resolve_benchmark_entry(structure, entry)
            predictor = HotspotPredictor(
                allele=entry.allele,
                peptide_chain=entry.peptide_chain,
                hla_chain=entry.hla_chain,
            )
            prediction = predictor.predict(entry.resolved_pdb_path, select_hotspots=False)
            contacts = extract_peptide_contact_positions(structure, entry, contact_mode=contact_mode)
            labels = {pos: 1 for pos in contacts}
            frame = build_training_frame(
                prediction,
                labels,
                pdb_id=entry.pdb_id,
                allele=entry.allele,
                peptide_length=prediction.peptide_length,
            )
            if not frame.empty:
                frames.append(frame)
        except Exception:
            logger.exception("Skipping training row for %s", entry.pdb_id)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
