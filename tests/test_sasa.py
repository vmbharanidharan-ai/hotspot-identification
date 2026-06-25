"""Tests for FreeSASA-backed SASA and surface-area features."""

import pytest
from Bio.PDB import PDBParser

from pmhc_hotspot.features.sasa import HAS_FREESASA, SASACalculator
from pmhc_hotspot.features.surface import (
    is_hydrophobic,
    is_polar,
    residue_surface_areas,
    residue_surface_from_sasa,
)


pytestmark = pytest.mark.skipif(not HAS_FREESASA, reason="FreeSASA not installed")


@pytest.fixture
def minimal_structure(fixture_pdb):
    return PDBParser(QUIET=True).get_structure("mini", fixture_pdb)


def test_compute_returns_positive_sasa_for_peptide(minimal_structure):
    calc = SASACalculator()
    result = calc.compute(minimal_structure)
    assert result.residue_sasa
    peptide_residues = list(minimal_structure[0]["P"])
    assert len(peptide_residues) == 9
    for residue in peptide_residues:
        assert calc.residue_sasa(residue, result) >= 0.0
        assert 0.0 <= calc.residue_relative_sasa(residue, result) <= 1.0


def test_apolar_polar_split_is_non_negative(minimal_structure):
    result = SASACalculator().compute(minimal_structure)
    for residue in minimal_structure[0]["P"]:
        apolar = result.residue_apolar_sasa[residue]
        polar = result.residue_polar_sasa[residue]
        total = result.residue_sasa[residue]
        assert apolar >= 0.0
        assert polar >= 0.0
        assert apolar + polar <= total + 1e-6


def test_residue_surface_from_sasa_fractions_sum_to_one(minimal_structure):
    calc = SASACalculator()
    result = calc.compute(minimal_structure)
    residue = minimal_structure[0]["P"][4]  # TYR
    surface = residue_surface_from_sasa(residue, result, aa="Y")
    assert surface.total_sasa > 0.0
    assert surface.hydrophobic_fraction + surface.polar_fraction == pytest.approx(1.0, abs=1e-6)


def test_aa_classification_fallback():
    hydro = residue_surface_areas(100.0, aa="L")
    polar = residue_surface_areas(100.0, aa="R")
    assert hydro.hydrophobic_fraction == 1.0
    assert polar.polar_fraction == 1.0
    assert is_hydrophobic("L")
    assert is_polar("R")
