"""Shared constants for pMHC hotspot selection."""

from __future__ import annotations

# Three-letter to one-letter amino acid map (standard 20).
THREE_TO_ONE: dict[str, str] = {
    "ALA": "A",
    "CYS": "C",
    "ASP": "D",
    "GLU": "E",
    "PHE": "F",
    "GLY": "G",
    "HIS": "H",
    "ILE": "I",
    "LYS": "K",
    "LEU": "L",
    "MET": "M",
    "ASN": "N",
    "PRO": "P",
    "GLN": "Q",
    "ARG": "R",
    "SER": "S",
    "THR": "T",
    "VAL": "V",
    "TRP": "W",
    "TYR": "Y",
}

# Hot-spot hierarchy for protein–protein interfaces (Trp > Arg > Tyr > ...).
# Based on alanine-scanning and interface energetics literature.
RESIDUE_CHEMICAL_SCORE: dict[str, float] = {
    "W": 10.0,
    "R": 9.0,
    "Y": 8.0,
    "F": 8.0,
    "K": 7.0,
    "D": 7.0,
    "E": 7.0,
    "M": 6.0,
    "L": 6.0,
    "I": 6.0,
    "H": 6.0,
    "V": 5.0,
    "C": 4.0,
    "T": 3.0,
    "S": 3.0,
    "N": 3.0,
    "Q": 3.0,
    "A": 1.0,
    "G": 0.0,
    "P": -10.0,
}

# Count toward the ">=3 hydrophobic residues" guideline for binder interfaces.
HYDROPHOBIC_FOR_INTERFACE = frozenset("WFYMLIVC")

# Poor design targets: rigid (Pro) or too small/flexible (Gly).
SKIP_ALWAYS = frozenset("GP")

# Max relative SASA (Å²) per residue type — Tien et al. 2013, extended set.
MAX_SASA: dict[str, float] = {
    "A": 129.0,
    "R": 274.0,
    "N": 195.0,
    "D": 193.0,
    "C": 167.0,
    "Q": 225.0,
    "E": 223.0,
    "G": 104.0,
    "H": 224.0,
    "I": 197.0,
    "L": 201.0,
    "K": 236.0,
    "M": 224.0,
    "F": 240.0,
    "P": 159.0,
    "S": 155.0,
    "T": 172.0,
    "W": 285.0,
    "Y": 263.0,
    "V": 174.0,
    "X": 200.0,
}

DEFAULT_WEIGHTS: dict[str, float] = {
    "sasa": 0.25,
    "protrusion": 0.18,
    "curvature": 0.08,
    "bulge": 0.08,
    "mutation": 0.12,
    "low_hla_contact": 0.12,
    "tcr_exposure": 0.10,
    "chemical": 0.05,
    "confidence": 0.02,
}

DEFAULT_HOTSPOT_CONFIG: dict[str, int] = {
    "min_hotspots": 3,
    "max_hotspots": 6,
    "min_hydrophobic": 3,
    "min_patch_size": 2,
    "max_patches": 3,
}

CONTACT_CUTOFF_A = 4.5
BURIED_HLA_CONTACT_THRESHOLD = 5
PROBE_RADIUS_A = 1.4

# Curated benchmark PDB IDs with peptide–MHC–TCR complexes (Phase 2).
BENCHMARK_PDB_IDS: list[str] = [
    "1A6Z",
    "2C5L",
    "3GHW",
    "2VLJ",
    "5NHT",
    "5NM8",
]
