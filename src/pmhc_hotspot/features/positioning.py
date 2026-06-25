"""Peptide residue indexing for variable-length peptides."""

from __future__ import annotations

from pmhc_hotspot.io import chain_ca_residues, residue_aa1


class PeptideResidueMap:
    """
    Map peptide chain residues to P1–Pn notation.

    Supports variable peptide lengths (8–15 residues typical for MHC-I).
    Also provides normalized position (0 = N-term, 1 = C-term) for
    cross-length comparisons.
    """

    def __init__(self, peptide_chain):
        self.chain_id = peptide_chain.id
        self.residues = chain_ca_residues(peptide_chain)
        self.sequence = "".join(residue_aa1(r) for r in self.residues)
        self.length = len(self.residues)

    def position_label(self, index: int) -> str:
        if index < 0 or index >= self.length:
            raise IndexError(f"Peptide index {index} out of range (length {self.length})")
        return f"P{index + 1}"

    def normalized_position(self, index: int) -> float:
        if self.length <= 1:
            return 0.0
        return index / (self.length - 1)

    def residue_to_index(self, residue) -> int:
        for i, r in enumerate(self.residues):
            if r is residue:
                return i
        raise KeyError("Residue not in peptide chain")

    def index_to_residue(self, index: int):
        return self.residues[index]

    def anchor_positions(self, allele: str | None = None) -> frozenset[int]:
        """Return 1-based anchor positions for this peptide length."""
        from pmhc_hotspot.features.allele_rules import get_anchor_positions

        return get_anchor_positions(allele, self.length)

    def preferred_tcr_positions(self) -> list[int]:
        """
        1-based positions likely TCR-accessible for this peptide length.

        For MHC-I, central bulge positions (roughly P3–P8) are preferred,
        excluding anchor positions.
        """
        anchors = self.anchor_positions()
        primary = [p for p in range(4, self.length) if p not in anchors]
        secondary = [3] if 3 not in anchors and self.length >= 3 else []
        return secondary + primary
