"""Solvent-accessible surface area estimation."""

from __future__ import annotations

import numpy as np

from pmhc_hotspot.constants import MAX_SASA, PROBE_RADIUS_A


class SASACalculator:
    """
    Estimate relative solvent accessibility per residue.

    Uses a neighbor-counting proxy (Lee & Richards style approximation)
    suitable for pure-Python deployment without FreeSASA. Values are
    normalized to [0, 1] using per-residue maximum SASA (Tien et al.).
    """

    def __init__(self, probe_radius: float = PROBE_RADIUS_A, neighbor_radius: float = 10.0):
        self.probe_radius = probe_radius
        self.neighbor_radius = neighbor_radius

    def _heavy_coords(self, residue) -> np.ndarray:
        coords = [a.coord for a in residue if a.element != "H"]
        return np.array(coords) if coords else np.empty((0, 3))

    def _all_coords(self, residues) -> np.ndarray:
        blocks = [self._heavy_coords(r) for r in residues]
        blocks = [b for b in blocks if len(b)]
        return np.vstack(blocks) if blocks else np.empty((0, 3))

    def absolute_sasa(self, residue, all_residues) -> float:
        """Neighbor-based SASA proxy in Å²."""
        res_coords = self._heavy_coords(residue)
        if len(res_coords) == 0:
            return 0.0

        all_coords = self._all_coords(all_residues)
        if len(all_coords) == 0:
            return float(len(res_coords) * 15.0)

        # Count neighbors within probe + neighbor radius
        from scipy.spatial.distance import cdist

        dists = cdist(res_coords, all_coords)
        # Self atoms at distance 0 — exclude same residue atoms from burial
        res_idx = all_residues.index(residue) if residue in all_residues else -1
        if res_idx >= 0:
            start = sum(len(self._heavy_coords(all_residues[i])) for i in range(res_idx))
            end = start + len(res_coords)
            dists[:, start:end] = np.inf

        buried_fraction = (dists < self.neighbor_radius).any(axis=1).mean()
        max_atoms = len(res_coords)
        exposed_atoms = (1.0 - buried_fraction) * max_atoms
        return float(exposed_atoms * 15.0)  # ~15 Å² per exposed heavy atom

    def relative_sasa(self, residue, all_residues, aa: str) -> float:
        """Relative SASA in [0, 1]."""
        abs_sasa = self.absolute_sasa(residue, all_residues)
        max_sasa = MAX_SASA.get(aa, MAX_SASA["X"])
        return float(min(1.0, max(0.0, abs_sasa / max_sasa)))
