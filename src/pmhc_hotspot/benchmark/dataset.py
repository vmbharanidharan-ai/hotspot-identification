"""Structure retrieval and TCR-contact label extraction."""

from __future__ import annotations

import logging
from pathlib import Path

from Bio.PDB import PDBList

from pmhc_hotspot.benchmark.contact_labels import (
    CONTACT_MODES,
    ContactMode,
    extract_contact_positions_via_generator,
)
from pmhc_hotspot.benchmark.manifest import BenchmarkEntry
from pmhc_hotspot.data.validation import safe_cache_path, validate_pdb_id
from pmhc_hotspot.features.positioning import PeptideResidueMap
from pmhc_hotspot.features.spatial import heavy_atoms
from pmhc_hotspot.io import chain_ca_residues, chain_residue_count, get_chain, get_model, infer_peptide_hla_chains

logger = logging.getLogger(__name__)


def chain_length_map(structure) -> dict[str, int]:
    """Map chain ID to standard amino-acid residue count."""
    model = get_model(structure)
    lengths: dict[str, int] = {}
    for chain in model:
        count = chain_residue_count(chain)
        if count > 0:
            lengths[chain.id] = count
    return lengths


def suggest_benchmark_chains(chain_lengths: dict[str, int]) -> dict[str, str | tuple[str, ...]] | None:
    """
    Infer peptide, MHC heavy, and TCR chains from residue counts.

    Returns None when no discrete MHC-I peptide chain (8-15 aa) is present.
    """
    peptide_candidates = [c for c, n in chain_lengths.items() if 8 <= n <= 15]
    if not peptide_candidates:
        return None

    peptide_chain = min(peptide_candidates, key=lambda c: chain_lengths[c])

    mhc_candidates = [
        (c, n)
        for c, n in chain_lengths.items()
        if c != peptide_chain and n >= 170
    ]
    if not mhc_candidates:
        mhc_candidates = [
            (c, n)
            for c, n in chain_lengths.items()
            if c != peptide_chain and 140 <= n <= 220
        ]
    if not mhc_candidates:
        return None
    hla_chain = max(mhc_candidates, key=lambda item: item[1])[0]

    known = {peptide_chain, hla_chain}
    known.update(
        c for c, n in chain_lengths.items() if c not in known and 85 <= n <= 110
    )

    tcr_candidates = [
        (c, n) for c, n in chain_lengths.items() if c not in known and n >= 80
    ]
    tcr_chains = tuple(
        c for c, _ in sorted(tcr_candidates, key=lambda item: item[1], reverse=True)[:2]
    )
    if not tcr_chains:
        return None

    return {
        "peptide_chain": peptide_chain,
        "hla_chain": hla_chain,
        "tcr_chains": tcr_chains,
    }


def resolve_benchmark_entry(structure, entry: BenchmarkEntry) -> BenchmarkEntry:
    """Use manifest chain IDs when valid; otherwise infer from structure composition."""
    lengths = chain_length_map(structure)
    manifest_valid = (
        entry.peptide_chain in lengths
        and entry.hla_chain in lengths
        and all(chain_id in lengths for chain_id in entry.tcr_chains)
    )
    if manifest_valid:
        return entry

    suggested = suggest_benchmark_chains(lengths)
    if suggested is None:
        raise ValueError(
            f"{entry.pdb_id}: could not resolve peptide/MHC/TCR chains "
            f"(found chain lengths: {lengths})"
        )

    logger.warning(
        "Manifest chain IDs invalid for %s; using inferred peptide=%s hla=%s tcr=%s",
        entry.pdb_id,
        suggested["peptide_chain"],
        suggested["hla_chain"],
        suggested["tcr_chains"],
    )
    return BenchmarkEntry(
        pdb_id=entry.pdb_id,
        allele=entry.allele,
        peptide_chain=str(suggested["peptide_chain"]),
        hla_chain=str(suggested["hla_chain"]),
        tcr_chains=tuple(str(c) for c in suggested["tcr_chains"]),
        pdb_path=entry.pdb_path,
        notes=entry.notes,
    )


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
        if fetched:
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

    def ensure_manifest_paths(
        self,
        entries: list[BenchmarkEntry],
        *,
        skip_missing: bool = True,
    ) -> list[BenchmarkEntry]:
        resolved: list[BenchmarkEntry] = []
        for entry in entries:
            path: str | None = entry.pdb_path
            if path and Path(path).exists() and Path(path).stat().st_size > 0:
                resolved.append(entry)
                continue
            try:
                path = str(self.download(entry.pdb_id))
            except (FileNotFoundError, OSError, ValueError) as exc:
                if skip_missing:
                    logger.warning("Skipping %s: %s", entry.pdb_id, exc)
                    continue
                raise
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


def extract_peptide_contact_positions(
    structure,
    entry: BenchmarkEntry,
    *,
    contact_mode: ContactMode = "standard",
) -> set[str]:
    """
    Return P-position labels for peptide residues contacting the TCR.

    Delegates to ContactLabelGenerator for vectorized labeling (Phase 0.2).
    """
    if contact_mode not in CONTACT_MODES:
        raise ValueError(f"contact_mode must be one of {CONTACT_MODES}")
    return extract_contact_positions_via_generator(structure, entry, contact_mode=contact_mode)
