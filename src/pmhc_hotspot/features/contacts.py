"""Peptide–MHC and peptide–peptide contact analysis."""

from __future__ import annotations

from pmhc_hotspot.constants import BURIED_HLA_CONTACT_THRESHOLD, CONTACT_CUTOFF_A
from pmhc_hotspot.features.spatial import count_cross_contacts, heavy_atoms


class ContactAnalyzer:
    """Count atomic contacts between peptide and MHC / peptide neighbors."""

    def __init__(self, cutoff: float = CONTACT_CUTOFF_A):
        self.cutoff = cutoff

    def count_contacts(self, res_a, residues_b: list) -> int:
        atoms_a = heavy_atoms(res_a)
        atoms_b = heavy_atoms(residues_b)
        return count_cross_contacts(atoms_a, atoms_b, self.cutoff)

    def hla_contacts(self, peptide_residue, hla_residues: list) -> int:
        return self.count_contacts(peptide_residue, hla_residues)

    def peptide_neighbors(self, peptide_residue, peptide_residues: list, index: int) -> int:
        others = [r for i, r in enumerate(peptide_residues) if i != index]
        return self.count_contacts(peptide_residue, others)

    def is_buried(
        self,
        peptide_residue,
        hla_residues: list,
        relative_sasa: float,
        *,
        contact_threshold: int = BURIED_HLA_CONTACT_THRESHOLD,
        sasa_threshold: float = 0.15,
    ) -> bool:
        """
        Buried in HLA groove if high MHC contact count OR very low SASA.

        Separates HLA burial from TCR-facing exposure.
        """
        contacts = self.hla_contacts(peptide_residue, hla_residues)
        return contacts >= contact_threshold or relative_sasa < sasa_threshold

    def normalized_hla_contact_burden(self, contact_count: int, max_contacts: int) -> float:
        """Normalize contact count to [0, 1] across peptide residues."""
        if max_contacts <= 0:
            return 0.0
        return float(min(1.0, contact_count / max_contacts))
