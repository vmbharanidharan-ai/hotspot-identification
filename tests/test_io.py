"""Tests for structure I/O."""

from pmhc_hotspot.io import StructureLoader, infer_peptide_hla_chains


def test_load_pdb(fixture_pdb):
    structure = StructureLoader().load(fixture_pdb)
    assert structure is not None


def test_infer_chains(fixture_pdb):
    structure = StructureLoader().load(fixture_pdb)
    pep, hla = infer_peptide_hla_chains(structure)
    assert pep == "P"
    assert "H" in hla
