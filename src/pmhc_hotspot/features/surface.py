"""Hydrophobic/polar surface-area features derived from SASA."""

from __future__ import annotations

from dataclasses import dataclass

from pmhc_hotspot.features.sasa import SASAResult

# Residue-level fallback groups when only total SASA is available.
HYDROPHOBIC_AA = frozenset({"A", "V", "I", "L", "M", "F", "W", "Y", "P"})
POLAR_AA = frozenset({"S", "T", "N", "Q", "C", "D", "E", "K", "R", "H", "G"})


@dataclass(frozen=True)
class ResidueSurfaceAreas:
    """Absolute and fractional hydrophobic/polar surface for one residue."""

    total_sasa: float
    hydrophobic_sasa: float
    polar_sasa: float
    hydrophobic_fraction: float
    polar_fraction: float


def is_hydrophobic(aa: str) -> bool:
    return aa.upper() in HYDROPHOBIC_AA


def is_polar(aa: str) -> bool:
    return aa.upper() in POLAR_AA


def _fraction(numerator: float, denominator: float) -> float:
    if denominator <= 0.0:
        return 0.0
    return max(0.0, min(1.0, numerator / denominator))


def residue_surface_areas(
    total_sasa: float,
    *,
    apolar_sasa: float | None = None,
    polar_sasa: float | None = None,
    aa: str | None = None,
) -> ResidueSurfaceAreas:
    """
    Build hydrophobic/polar surface breakdown for a residue.

  Prefer FreeSASA apolar/polar splits when provided; otherwise classify the
  full residue SASA by amino-acid type.
    """
    total = max(0.0, float(total_sasa))
    if apolar_sasa is not None and polar_sasa is not None:
        hydro = max(0.0, float(apolar_sasa))
        polar = max(0.0, float(polar_sasa))
    elif aa is not None and is_hydrophobic(aa):
        hydro = total
        polar = 0.0
    elif aa is not None:
        hydro = 0.0
        polar = total
    else:
        hydro = 0.0
        polar = 0.0

    return ResidueSurfaceAreas(
        total_sasa=total,
        hydrophobic_sasa=hydro,
        polar_sasa=polar,
        hydrophobic_fraction=_fraction(hydro, total),
        polar_fraction=_fraction(polar, total),
    )


def residue_surface_from_sasa(
    residue,
    sasa_result: SASAResult,
    *,
    aa: str | None = None,
) -> ResidueSurfaceAreas:
    """Convenience wrapper around a SASAResult row."""
    total = float(sasa_result.residue_sasa.get(residue, 0.0))
    apolar = sasa_result.residue_apolar_sasa.get(residue)
    polar = sasa_result.residue_polar_sasa.get(residue)
    if apolar is None or polar is None:
        return residue_surface_areas(total, aa=aa)
    return residue_surface_areas(total, apolar_sasa=apolar, polar_sasa=polar, aa=aa)
