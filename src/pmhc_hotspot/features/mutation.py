"""Mutation proximity scoring for neoantigen contexts."""

from __future__ import annotations


class MutationScorer:
    """
    Soft bias toward residues near neoantigen mutations.

    Mutation presence does NOT imply immunogenicity or TCR accessibility;
    this term is a design prioritization hint only.
    """

    def __init__(self, mutation_positions: list[int] | None = None, window: int = 2):
        """
        Parameters
        ----------
        mutation_positions
            0-based peptide indices with somatic mutations.
        window
            Positions within this distance receive partial credit.
        """
        self.mutation_positions = mutation_positions or []
        self.window = window

    def proximity(self, pos_idx: int) -> float:
        if not self.mutation_positions:
            return 0.0
        dist = min(abs(pos_idx - m) for m in self.mutation_positions)
        if dist > self.window:
            return 0.0
        return float(max(0.0, 1.0 - dist / (self.window + 1)))

    @staticmethod
    def parse_mutation_positions(tokens: list[str], peptide_length: int) -> list[int]:
        """Parse P5, 5, or 5-based indices to 0-based positions."""
        positions: list[int] = []
        for token in tokens:
            t = token.strip().upper()
            if t.startswith("P"):
                idx = int(t[1:]) - 1
            else:
                idx = int(t) - 1
            if 0 <= idx < peptide_length:
                positions.append(idx)
        return positions
