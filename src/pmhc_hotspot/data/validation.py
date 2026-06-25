"""Input validation for external data sources."""

from __future__ import annotations

import re
from pathlib import Path

PDB_ID_RE = re.compile(r"^[0-9][A-Za-z0-9]{3}$")
STANDARD_AA_RE = re.compile(r"^[ACDEFGHIKLMNPQRSTVWY]+$")


def validate_pdb_id(pdb_id: str) -> str:
    """Validate and normalize a four-character PDB identifier."""
    pid = pdb_id.strip().upper()
    if not PDB_ID_RE.match(pid):
        raise ValueError(f"Invalid PDB ID format: {pdb_id!r}")
    return pid


def safe_cache_path(cache_dir: str | Path, filename: str) -> Path:
    """Resolve a path inside a cache directory (prevents path traversal)."""
    root = Path(cache_dir).resolve()
    target = (root / filename).resolve()
    if root not in target.parents and target != root:
        raise ValueError(f"Unsafe cache path: {filename}")
    return target


def validate_peptide_sequence(peptide: str) -> str:
    seq = peptide.strip().upper()
    if not seq:
        raise ValueError("Empty peptide sequence")
    if not STANDARD_AA_RE.match(seq):
        raise ValueError(f"Non-standard peptide sequence: {peptide!r}")
    if len(seq) < 8 or len(seq) > 15:
        raise ValueError(f"Peptide length {len(seq)} outside supported MHC-I range (8-15)")
    return seq
