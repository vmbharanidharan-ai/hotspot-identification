"""Structure confidence weighting from B-factors or pLDDT."""

from __future__ import annotations


class ConfidenceScorer:
    """
    Downweight residues with poor coordinate quality.

    Reads B-factors from PDB (high B = low confidence in many models).
    If pLDDT is stored in B-factor column (AlphaFold convention), rescales.
    """

    def __init__(self, plddt_in_bfactor: bool = True):
        self.plddt_in_bfactor = plddt_in_bfactor

    def residue_confidence(self, residue) -> float:
        if "CA" not in residue:
            return 0.5
        bfactor = residue["CA"].bfactor
        if self.plddt_in_bfactor and bfactor <= 100:
            # AlphaFold pLDDT in B-factor column
            return float(min(1.0, max(0.0, bfactor / 100.0)))
        # Crystallographic B-factor: lower is better; typical range 10–80
        return float(min(1.0, max(0.1, 1.0 - (bfactor - 10.0) / 100.0)))

    @staticmethod
    def is_low_confidence(score: float, threshold: float = 0.5) -> bool:
        """Flag structurally uncertain residues before scoring or ML training."""
        return score < threshold
