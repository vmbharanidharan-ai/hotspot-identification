"""Curated benchmark PDB dataset."""

from __future__ import annotations

import urllib.request
from pathlib import Path

from pmhc_hotspot.constants import BENCHMARK_PDB_IDS


class PDBDataset:
    """Download and cache benchmark pMHC structures from RCSB PDB."""

    def __init__(self, cache_dir: str | Path = "data/pdb"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def pdb_path(self, pdb_id: str) -> Path:
        return self.cache_dir / f"{pdb_id.upper()}.pdb"

    def download(self, pdb_id: str) -> Path:
        pdb_id = pdb_id.upper()
        out = self.pdb_path(pdb_id)
        if out.exists():
            return out
        url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
        urllib.request.urlretrieve(url, out)
        return out

    def download_all(self, pdb_ids: list[str] | None = None) -> list[Path]:
        ids = pdb_ids or BENCHMARK_PDB_IDS
        return [self.download(pid) for pid in ids]
