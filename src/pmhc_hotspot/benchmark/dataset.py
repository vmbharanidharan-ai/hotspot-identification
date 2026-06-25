"""Structure retrieval and TCR-contact label extraction."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from Bio.PDB import PDBList
from scipy.spatial.distance import cdist

from pmhc_hotspot.benchmark.manifest import BenchmarkEntry
from pmhc_hotspot.constants import CONTACT_CUTOFF_A
from pmhc_hotspot.data.validation import safe_cache_path, validate_pdb_id
from pmhc_hotspot.features.positioning import PeptideResidueMap
from pmhc_hotspot.io import chain_ca_residues, get_chain, infer_peptide_hla_chains

logger = logging.getLogger(__name__)


class PDBDownloader:
    """Download PDB files via Biopython PDBList."""

    def __init__(self, cache_dir: str | Path = "data/pdb"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._pdbl = PDBList()

    def pdb_path(self, pdb_id: str) -> Path:
        pdb_id = validate_pdb_id(pdb_id)
        return safe_cache_path(self.cache_dir, f"{pdb_id}.pdb")

    def download(self, pdb_id: str) -> Path:
        pdb_id = validate_pdb_id(pdb_id)
        out = self.pdb_path(pdb_id)
        if out.exists() and out.stat().st_size > 0:
            return out
        logger.info("Downloading PDB %s", pdb_id)
        fetched = self._pdbl.retrieve_pdb_file(
            pdb_id,
            pdir=str(self.cache_dir),
            file_format="pdb",
            overwrite=False,
        )
        fetched_path = Path(fetched)
        if fetched_path.exists() and fetched_path != out:
            if out.exists():
                out.unlink()
            fetched_path.rename(out)
        if not out.exists():
            alt = self.cache_dir / f"pdb{pdb_id.lower()}.ent"
            if alt.exists():
                alt.rename(out)
        if not out.exists():
            raise FileNotFoundError(f"Failed to download PDB {pdb_id}")
        return out

    def ensure_manifest_paths(self, entries: list[BenchmarkEntry]) -> list[BenchmarkEntry]:
        resolved: list[BenchmarkEntry] = []
        for entry in entries:
            path = entry.pdb_path or str(self.download(entry.pdb_id))
            resolved.append(
                BenchmarkEntry(
                    pdb_id=entry.pdb_id,
                    allele=entry.allele,
                    peptide_chain=entry.peptide_chain,
                    hla_chain=entry.hla_chain,
                    tcr_chains=entry.tcr_chains,
                    pdb_path=path,
                    notes=entry.notes,
                )
            )
        return resolved


def _heavy_coords(residue) -> np.ndarray:
    coords = [a.coord for a in residue if a.element != "H"]
    return np.array(coords) if coords else np.empty((0, 3))


def _chain_heavy_coords(chain) -> np.ndarray:
    blocks = [_heavy_coords(r) for r in chain_ca_residues(chain)]
    blocks = [b for b in blocks if len(b)]
    return np.vstack(blocks) if blocks else np.empty((0, 3))


def extract_peptide_contact_positions(structure, entry: BenchmarkEntry) -> set[str]:
    """
    Return P-position labels for peptide residues within CONTACT_CUTOFF_A of TCR.

  Ground truth for TCR-contact recovery benchmarks.
    """
    pep_id, hla_ids = infer_peptide_hla_chains(
        structure,
        entry.peptide_chain,
        entry.hla_chain,
    )
    pep_chain = get_chain(structure, pep_id)
    prm = PeptideResidueMap(pep_chain)

    tcr_chains = list(entry.tcr_chains)
    if not tcr_chains:
        model = structure[0]
        known = {pep_id, *hla_ids}
        tcr_chains = [
            chain.id
            for chain in model
            if chain.id not in known and len(chain_ca_residues(chain)) >= 80
        ]

    tcr_coords = []
    for chain_id in tcr_chains:
        try:
            chain = get_chain(structure, chain_id)
        except ValueError:
            logger.warning("TCR chain %s missing in %s", chain_id, entry.pdb_id)
            continue
        coords = _chain_heavy_coords(chain)
        if len(coords):
            tcr_coords.append(coords)

    if not tcr_coords:
        logger.warning("No TCR coordinates for %s", entry.pdb_id)
        return set()

    tcr_all = np.vstack(tcr_coords)
    contacted: set[str] = set()

    for i, residue in enumerate(prm.residues):
        res_coords = _heavy_coords(residue)
        if len(res_coords) == 0:
            continue
        dists = cdist(res_coords, tcr_all)
        if (dists <= CONTACT_CUTOFF_A).any():
            contacted.add(prm.position_label(i))

    return contacted
