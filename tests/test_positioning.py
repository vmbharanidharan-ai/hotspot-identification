"""Tests for peptide positioning."""

from pmhc_hotspot.features.positioning import PeptideResidueMap
from pmhc_hotspot.io import StructureLoader, get_chain, infer_peptide_hla_chains


def test_variable_length_mapping(fixture_pdb):
    structure = StructureLoader().load(fixture_pdb)
    pep_id, _ = infer_peptide_hla_chains(structure)
    prm = PeptideResidueMap(get_chain(structure, pep_id))
    assert prm.length == 9
    assert prm.position_label(0) == "P1"
    assert prm.position_label(8) == "P9"
    assert prm.normalized_position(0) == 0.0
    assert prm.normalized_position(8) == 1.0
