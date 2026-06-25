"""Spatial indexing helpers built on BioPython NeighborSearch."""

from __future__ import annotations

import numpy as np
from Bio.PDB.NeighborSearch import NeighborSearch

_BACKBONE = frozenset({"N", "CA", "C", "O", "OXT"})


def heavy_atoms(residues) -> list:
    """Collect non-hydrogen atoms from one or more residues."""
    if not isinstance(residues, (list, tuple)):
        residues = [residues]
    atoms = []
    for residue in residues:
        for atom in residue:
            if atom.element != "H":
                atoms.append(atom)
    return atoms


def count_cross_contacts(atoms_a: list, atoms_b: list, cutoff: float) -> int:
    """
    Count atom–atom pairs with interatomic distance <= cutoff.

    Uses BioPython NeighborSearch on ``atoms_b`` for efficient queries.
    """
    if not atoms_a or not atoms_b:
        return 0
    ns = NeighborSearch(atoms_b)
    b_ids = {id(atom) for atom in atoms_b}
    count = 0
    for atom in atoms_a:
        for neighbor in ns.search(atom.coord, cutoff):
            if id(neighbor) in b_ids:
                count += 1
    return count


def min_inter_atomic_distance(atoms_a: list, atoms_b: list, search_radius: float = 12.0) -> float:
    """Minimum heavy-atom distance between two atom lists (Å)."""
    if not atoms_a or not atoms_b:
        return float("inf")
    ns = NeighborSearch(atoms_b)
    min_dist = float("inf")
    for atom in atoms_a:
        for neighbor in ns.search(atom.coord, search_radius):
            dist = float(np.linalg.norm(np.asarray(atom.coord) - np.asarray(neighbor.coord)))
            if dist < min_dist:
                min_dist = dist
    return min_dist


def peptide_tcr_contact_pairs(
    peptide_residue,
    tcr_atoms: list,
    *,
    max_distance: float,
) -> list[tuple[float, bool, bool]]:
    """
    Return (distance, peptide_sidechain, tcr_sidechain) for atom pairs within max_distance.

    Uses NeighborSearch on TCR atoms; only pairs within ``max_distance`` are returned.
    """
    pep_atoms = heavy_atoms(peptide_residue)
    if not pep_atoms or not tcr_atoms:
        return []

    ns = NeighborSearch(tcr_atoms)
    pairs: list[tuple[float, bool, bool]] = []
    for atom in pep_atoms:
        pep_sidechain = atom.name not in _BACKBONE
        for neighbor in ns.search(atom.coord, max_distance):
            tcr_sidechain = neighbor.name not in _BACKBONE
            dist = float(np.linalg.norm(np.asarray(atom.coord) - np.asarray(neighbor.coord)))
            pairs.append((dist, pep_sidechain, tcr_sidechain))
    return pairs
