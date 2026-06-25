"""Tests for structure validation."""

from pmhc_hotspot.io import StructureLoader
from pmhc_hotspot.validation import StructureValidator


def test_validation_passes(fixture_pdb):
    structure = StructureLoader().load(fixture_pdb)
    report = StructureValidator().validate(structure)
    assert report.ok
