"""Structure loading utilities."""

from __future__ import annotations

from pathlib import Path

from Bio.PDB import MMCIFParser, PDBParser
from Bio.PDB.Structure import Structure


class StructureLoader:
    """Load PDB or mmCIF structures via Biopython."""

    def load(self, path: str | Path) -> Structure:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Structure file not found: {p}")

        suffix = p.suffix.lower()
        if suffix in {".cif", ".mmcif"}:
            parser = MMCIFParser(QUIET=True)
        elif suffix in {".pdb", ".ent"}:
            parser = PDBParser(QUIET=True)
        else:
            raise ValueError(f"Unsupported structure format: {suffix}")

        return parser.get_structure(p.stem, str(p))


def get_model(structure: Structure):
    """Return the first model from a Biopython Structure."""
    return next(structure.get_models())


def iter_chains(structure: Structure):
    """Yield all chains in the first model."""
    model = get_model(structure)
    yield from model.get_chains()


def residue_aa1(residue) -> str:
    """One-letter amino acid code for a Biopython Residue."""
    from pmhc_hotspot.constants import THREE_TO_ONE

    resname = residue.get_resname().strip().upper()
    return THREE_TO_ONE.get(resname, "X")


def chain_residue_count(chain) -> int:
    """Count standard amino-acid residues in a chain."""
    return sum(1 for r in chain if r.id[0] == " ")


def chain_ca_residues(chain) -> list:
    """Ordered standard residues with CA atoms."""
    residues = [r for r in chain if r.id[0] == " " and "CA" in r]
    return sorted(residues, key=lambda r: (r.id[1], r.id[2].strip()))


def infer_peptide_hla_chains(
    structure: Structure,
    peptide_chain: str | None = None,
    hla_chain: str | None = None,
) -> tuple[str, list[str]]:
    """
    Infer peptide (short) and HLA (long) chain IDs.

    For typical two-chain pMHC complexes, the shortest chain is the peptide.
    For multi-chain complexes, the shortest non-empty chain is peptide and
    remaining protein chains are treated as MHC.
    """
    model = get_model(structure)
    chain_lengths = {chain.id: chain_residue_count(chain) for chain in model}
    chain_lengths = {k: v for k, v in chain_lengths.items() if v > 0}

    if not chain_lengths:
        raise ValueError("No protein chains found in structure")

    if peptide_chain and hla_chain:
        if peptide_chain not in chain_lengths:
            raise ValueError(f"Peptide chain {peptide_chain} not found")
        if hla_chain not in chain_lengths:
            raise ValueError(f"HLA chain {hla_chain} not found")
        return peptide_chain, [hla_chain]

    if peptide_chain:
        if peptide_chain not in chain_lengths:
            raise ValueError(f"Peptide chain {peptide_chain} not found")
        hla_ids = [c for c in chain_lengths if c != peptide_chain]
        if not hla_ids:
            raise ValueError("Could not identify HLA chain(s)")
        return peptide_chain, sorted(hla_ids, key=lambda c: chain_lengths[c], reverse=True)

    sorted_by_len = sorted(chain_lengths.items(), key=lambda x: x[1])
    pep = sorted_by_len[0][0]
    hla_ids = [c for c, _ in sorted_by_len[1:]]
    if not hla_ids:
        raise ValueError("Expected at least two chains (peptide + MHC)")
    return pep, sorted(hla_ids, key=lambda c: chain_lengths[c], reverse=True)


def get_chain(structure: Structure, chain_id: str):
    model = get_model(structure)
    for chain in model:
        if chain.id == chain_id:
            return chain
    raise ValueError(f"Chain {chain_id} not found")
