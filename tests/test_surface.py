"""Tests for hydrophobic/polar surface classification helpers."""

from pmhc_hotspot.features.surface import HYDROPHOBIC_AA, POLAR_AA, residue_surface_areas


def test_standard_amino_acids_partitioned():
    overlap = HYDROPHOBIC_AA & POLAR_AA
    assert not overlap


def test_fractions_for_mixed_free_sasa_split():
    surface = residue_surface_areas(80.0, apolar_sasa=30.0, polar_sasa=50.0)
    assert surface.hydrophobic_fraction == 0.375
    assert surface.polar_fraction == 0.625
