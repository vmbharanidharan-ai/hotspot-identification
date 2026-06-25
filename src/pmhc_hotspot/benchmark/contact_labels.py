"""Tiered TCR–peptide contact definitions for benchmark ground truth."""

from __future__ import annotations

from typing import Literal

import numpy as np
from scipy.spatial.distance import cdist

from pmhc_hotspot.constants import CONTACT_CUTOFF_A

ContactMode = Literal["strict", "standard", "permissive"]

CONTACT_MODES: tuple[str, ...] = ("strict", "standard", "permissive")

STRICT_CUTOFF_A = 3.5
STANDARD_CUTOFF_A = CONTACT_CUTOFF_A  # 4.5
PERMISSIVE_CUTOFF_A = 5.0

_BACKBONE = frozenset({"N", "CA", "C", "O", "OXT"})


def _atom_coords_and_names(residue) -> tuple[np.ndarray, list[str]]:
    coords = []
    names = []
    for atom in residue:
        if atom.element == "H":
            continue
        coords.append(atom.coord)
        names.append(atom.name)
    if not coords:
        return np.empty((0, 3)), []
    return np.array(coords), names


def _peptide_tcr_contact_pairs(
    peptide_residue,
    tcr_coords: np.ndarray,
    tcr_atom_names: list[str] | None = None,
) -> list[tuple[float, bool, bool]]:
    """
    Return (distance, peptide_sidechain, tcr_sidechain) for qualifying atom pairs.

    If tcr_atom_names is None, TCR atoms are treated as sidechain-capable (conservative).
    """
    pep_coords, pep_names = _atom_coords_and_names(peptide_residue)
    if len(pep_coords) == 0 or len(tcr_coords) == 0:
        return []

    if tcr_atom_names is None:
        tcr_sidechain_mask = np.ones(len(tcr_coords), dtype=bool)
    else:
        tcr_sidechain_mask = np.array([n not in _BACKBONE for n in tcr_atom_names])

    pep_sidechain_mask = np.array([n not in _BACKBONE for n in pep_names])
    dists = cdist(pep_coords, tcr_coords)

    pairs: list[tuple[float, bool, bool]] = []
    for i in range(dists.shape[0]):
        for j in range(dists.shape[1]):
            pairs.append(
                (
                    float(dists[i, j]),
                    bool(pep_sidechain_mask[i]),
                    bool(tcr_sidechain_mask[j]),
                )
            )
    return pairs


def residue_is_contact(pairs: list[tuple[float, bool, bool]], mode: ContactMode) -> bool:
    """Apply contact-mode rules to atom pair list for one peptide residue."""
    if not pairs:
        return False

    if mode == "permissive":
        return any(d <= PERMISSIVE_CUTOFF_A for d, _, _ in pairs)

    if mode == "standard":
        for d, pep_sc, tcr_sc in pairs:
            if d > STANDARD_CUTOFF_A:
                continue
            if pep_sc or tcr_sc:
                return True
            if d <= STRICT_CUTOFF_A:
                return True
        return False

    # strict: close side-chain-involved contacts only
    for d, pep_sc, tcr_sc in pairs:
        if d <= STRICT_CUTOFF_A and pep_sc:
            return True
    return False


def describe_contact_mode(mode: ContactMode) -> str:
    descriptions = {
        "permissive": f"any heavy-atom pair <= {PERMISSIVE_CUTOFF_A} A",
        "standard": (
            f"<= {STANDARD_CUTOFF_A} A with peptide or TCR side-chain involvement, "
            f"or <= {STRICT_CUTOFF_A} A backbone pairs"
        ),
        "strict": f"<= {STRICT_CUTOFF_A} A with peptide side-chain involvement",
    }
    return descriptions[mode]
