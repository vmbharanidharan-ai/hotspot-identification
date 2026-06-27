"""Tiered TCR–peptide contact definitions for benchmark ground truth."""

from __future__ import annotations

from typing import Literal

from pmhc_hotspot.constants import CONTACT_CUTOFF_A
from pmhc_hotspot.features.spatial import peptide_tcr_contact_pairs

ContactMode = Literal["strict", "standard", "permissive"]

CONTACT_MODES: tuple[str, ...] = ("strict", "standard", "permissive")

STRICT_CUTOFF_A = 3.5
STANDARD_CUTOFF_A = CONTACT_CUTOFF_A  # 4.5
PERMISSIVE_CUTOFF_A = 5.0


def _peptide_tcr_contact_pairs(
    peptide_residue,
    tcr_atoms: list,
) -> list[tuple[float, bool, bool]]:
    """
    Return (distance, peptide_sidechain, tcr_sidechain) for qualifying atom pairs.

    Uses BioPython NeighborSearch on TCR atoms (pairs up to permissive cutoff).
    """
    return peptide_tcr_contact_pairs(
        peptide_residue,
        tcr_atoms,
        max_distance=PERMISSIVE_CUTOFF_A,
    )


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


def extract_contact_positions_via_generator(
    structure,
    entry,
    *,
    contact_mode: ContactMode = "standard",
) -> set[str]:
    """Delegate peptide contact labeling to ContactLabelGenerator (Phase 0.2)."""
    from pmhc_hotspot.automation.label_generator import ContactLabelGenerator

    payload = ContactLabelGenerator(contact_mode=contact_mode).label_structure_object(
        structure,
        pdb_id=entry.pdb_id,
        peptide_chain=entry.peptide_chain,
        hla_chain=entry.hla_chain,
        tcr_chains=list(entry.tcr_chains),
    )
    return {
        pos
        for pos, row in payload.get("residues", {}).items()
        if row.get("is_tcr_contact")
    }
