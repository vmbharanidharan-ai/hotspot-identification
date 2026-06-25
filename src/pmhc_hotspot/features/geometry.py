"""Geometric features: protrusion, curvature, bulge."""

from __future__ import annotations

import numpy as np

from pmhc_hotspot.features.spatial import heavy_atoms, min_inter_atomic_distance


class GeometryCalculator:
    """
    Compute peptide surface geometry features.

    - protrusion: residue centroid distance above local peptide neighborhood
    - curvature: local backbone deviation from linear interpolation
    - bulge: Cα displacement from fitted local backbone (TCR-facing bulge proxy)
    """

    def __init__(self, neighbor_window: int = 2):
        self.neighbor_window = neighbor_window

    def ca_coord(self, residue) -> np.ndarray | None:
        if "CA" in residue:
            return residue["CA"].coord.copy()
        return None

    def residue_centroid(self, residue) -> np.ndarray:
        coords = [a.coord for a in residue if a.element != "H"]
        if not coords:
            ca = self.ca_coord(residue)
            return ca if ca is not None else np.zeros(3)
        return np.mean(coords, axis=0)

    def protrusion(self, index: int, peptide_residues: list) -> float:
        """How much residue protrudes from local peptide surface (Å, normalized later)."""
        if index < 0 or index >= len(peptide_residues):
            return 0.0
        center = self.residue_centroid(peptide_residues[index])
        lo = max(0, index - self.neighbor_window)
        hi = min(len(peptide_residues), index + self.neighbor_window + 1)
        neighbors = [self.residue_centroid(peptide_residues[i]) for i in range(lo, hi) if i != index]
        if not neighbors:
            return 0.0
        local_mean = np.mean(neighbors, axis=0)
        return float(np.linalg.norm(center - local_mean))

    def curvature(self, index: int, peptide_residues: list) -> float:
        """Local backbone curvature from three consecutive Cα atoms."""
        if len(peptide_residues) < 3 or index == 0 or index >= len(peptide_residues) - 1:
            return 0.0
        prev_ca = self.ca_coord(peptide_residues[index - 1])
        curr_ca = self.ca_coord(peptide_residues[index])
        next_ca = self.ca_coord(peptide_residues[index + 1])
        if prev_ca is None or curr_ca is None or next_ca is None:
            return 0.0
        v1 = prev_ca - curr_ca
        v2 = next_ca - curr_ca
        n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
        if n1 < 1e-6 or n2 < 1e-6:
            return 0.0
        cos_angle = np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0)
        angle = np.arccos(cos_angle)
        return float(np.pi - angle)

    def bulge(self, index: int, peptide_residues: list) -> float:
        """
        Cα displacement from local backbone line.

        Central peptide bulges are often TCR-contacted even when
        overall SASA is moderate (Rudolph et al.; recent pMHC dynamics work).
        """
        lo = max(0, index - self.neighbor_window)
        hi = min(len(peptide_residues) - 1, index + self.neighbor_window)
        if hi <= lo:
            return 0.0
        start_ca = self.ca_coord(peptide_residues[lo])
        end_ca = self.ca_coord(peptide_residues[hi])
        curr_ca = self.ca_coord(peptide_residues[index])
        if start_ca is None or end_ca is None or curr_ca is None:
            return 0.0
        line = end_ca - start_ca
        line_len = np.linalg.norm(line)
        if line_len < 1e-6:
            return 0.0
        t = np.dot(curr_ca - start_ca, line) / (line_len**2)
        t = np.clip(t, 0.0, 1.0)
        projected = start_ca + t * line
        return float(np.linalg.norm(curr_ca - projected))

    def distance_to_hla_surface(self, residue, hla_residues: list) -> float:
        """Minimum distance from residue heavy atoms to any HLA heavy atom."""
        res_atoms = heavy_atoms(residue)
        hla_atoms = heavy_atoms(hla_residues)
        min_dist = min_inter_atomic_distance(res_atoms, hla_atoms)
        return 999.0 if min_dist == float("inf") else float(min_dist)

    def tcr_exposure_prior(self, index: int, peptide_residues: list, preferred_positions: list[int]) -> float:
        """Biological prior for TCR-facing positions and favorable chemistry."""
        from pmhc_hotspot.constants import RESIDUE_CHEMICAL_SCORE
        from pmhc_hotspot.io import residue_aa1

        position_1based = index + 1
        aa = residue_aa1(peptide_residues[index])
        chem = RESIDUE_CHEMICAL_SCORE.get(aa, 0.0) / 10.0

        if position_1based in preferred_positions:
            pos_bonus = 1.0
        elif position_1based == 1:
            pos_bonus = 0.2
        else:
            pos_bonus = 0.5

        return float(0.6 * pos_bonus + 0.4 * chem)
