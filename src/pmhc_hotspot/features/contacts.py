"""Peptide–MHC and peptide–peptide contact analysis."""

from __future__ import annotations

import numpy as np
from scipy.spatial.distance import cdist

from pmhc_hotspot.constants import BURIED_HLA_CONTACT_THRESHOLD, CONTACT_CUTOFF_A


class ContactAnalyzer:
    """Count atomic contacts between peptide and MHC / peptide neighbors."""

    def __init__(self, cutoff: float = CONTACT_CUTOFF_A):
        self.cutoff = cutoff

    def _heavy_coords(self, residue) -> np.ndarray:
        coords = [a.coord for a in residue if a.element != "H"]
        return np.array(coords) if coords else np.empty((0, 3))

    def count_contacts(self, res_a, residues_b: list) -> int:
        a = self._heavy_coords(res_a)
        if len(a) == 0:
            return 0
        blocks = [self._heavy_coords(r) for r in residues_b]
        blocks = [b for b in blocks if len(b)]
        if not blocks:
            return 0
        b = np.vstack(blocks)
        d = cdist(a, b)
        return int((d <= self.cutoff).sum())

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

        Separates HLA burial from TCR-facing exposure (Perplexity correction).
        """
        contacts = self.hla_contacts(peptide_residue, hla_residues)
        return contacts >= contact_threshold or relative_sasa < sasa_threshold

    def normalized_hla_contact_burden(self, contact_count: int, max_contacts: int) -> float:
        """Normalize contact count to [0, 1] across peptide residues."""
        if max_contacts <= 0:
            return 0.0
        return float(min(1.0, contact_count / max_contacts))
