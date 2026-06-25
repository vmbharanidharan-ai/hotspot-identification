"""SASA-based exposure features using FreeSASA."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    import freesasa

    HAS_FREESASA = True
except Exception:  # pragma: no cover
    freesasa = None
    HAS_FREESASA = False


@dataclass
class SASAResult:
    """Container for residue-level SASA outputs."""

    residue_sasa: Dict[object, float]
    residue_relative_sasa: Dict[object, float]
    residue_apolar_sasa: Dict[object, float]
    residue_polar_sasa: Dict[object, float]


class SASACalculator:
    """
    Compute solvent-accessible surface area for residues using FreeSASA.

    Notes
    -----
    - Uses FreeSASA's Biopython bridge when possible.
    - Stores absolute SASA in Å².
    - Relative SASA and apolar/polar splits come from FreeSASA residue areas.
    """

    def __init__(
        self,
        probe_radius: float = 1.4,
        n_points: int = 100,
        classifier: Optional[Any] = None,
    ):
        self.probe_radius = probe_radius
        self.n_points = n_points
        self.classifier = classifier

    def _compute_from_biopdb(self, structure) -> SASAResult:
        if not HAS_FREESASA:
            raise ImportError(
                "FreeSASA is not installed. Install with `pip install freesasa` "
                "or `conda install -c conda-forge freesasa`."
            )

        fs_structure = freesasa.structureFromBioPDB(structure)
        params = freesasa.Parameters()
        params.setProbeRadius(self.probe_radius)
        params.setNPoints(self.n_points)

        result = freesasa.calc(fs_structure, params)
        residue_areas = result.residueAreas()

        residue_sasa: Dict[object, float] = {}
        residue_relative_sasa: Dict[object, float] = {}
        residue_apolar_sasa: Dict[object, float] = {}
        residue_polar_sasa: Dict[object, float] = {}

        bio_models = list(structure)
        if not bio_models:
            return SASAResult(
                residue_sasa,
                residue_relative_sasa,
                residue_apolar_sasa,
                residue_polar_sasa,
            )

        model = bio_models[0]
        for chain in model:
            chain_id = chain.id
            for residue in chain:
                if residue.id[0] != " ":
                    continue
                resseq = residue.id[1]
                key = str(resseq)
                try:
                    area = residue_areas[chain_id][key]
                    abs_sasa = float(area.total)
                    rel_sasa = float(area.relativeTotal)
                    apolar = float(area.apolar)
                    polar = float(area.polar)
                except Exception:
                    abs_sasa = 0.0
                    rel_sasa = 0.0
                    apolar = 0.0
                    polar = 0.0
                residue_sasa[residue] = abs_sasa
                residue_relative_sasa[residue] = max(0.0, min(1.0, rel_sasa))
                residue_apolar_sasa[residue] = max(0.0, apolar)
                residue_polar_sasa[residue] = max(0.0, polar)

        return SASAResult(
            residue_sasa,
            residue_relative_sasa,
            residue_apolar_sasa,
            residue_polar_sasa,
        )

    def compute(self, structure) -> SASAResult:
        """
        Compute residue-level SASA for all standard residues in model 0.

        Returns
        -------
        SASAResult
            Maps residue objects to absolute/relative SASA and apolar/polar splits.
        """
        return self._compute_from_biopdb(structure)

    def residue_sasa(self, residue, sasa_result: SASAResult) -> float:
        return float(sasa_result.residue_sasa.get(residue, 0.0))

    def residue_relative_sasa(self, residue, sasa_result: SASAResult) -> float:
        return float(sasa_result.residue_relative_sasa.get(residue, 0.0))

    def residue_apolar_sasa(self, residue, sasa_result: SASAResult) -> float:
        return float(sasa_result.residue_apolar_sasa.get(residue, 0.0))

    def residue_polar_sasa(self, residue, sasa_result: SASAResult) -> float:
        return float(sasa_result.residue_polar_sasa.get(residue, 0.0))
