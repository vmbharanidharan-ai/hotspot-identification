"""Backward-compatible re-export."""

from pmhc_hotspot.benchmark.dataset import PDBDownloader, extract_peptide_contact_positions

PDBDataset = PDBDownloader

__all__ = ["PDBDataset", "PDBDownloader", "extract_peptide_contact_positions"]
