"""Tests for BioPython NeighborSearch spatial helpers."""

from Bio.PDB import Atom, Residue

from pmhc_hotspot.features.contacts import ContactAnalyzer
from pmhc_hotspot.features.spatial import count_cross_contacts, heavy_atoms, min_inter_atomic_distance


def _atom(name: str, xyz: tuple[float, float, float], element: str = "C") -> Atom.Atom:
    atom = Atom.Atom(name, xyz, 1.0, 1.0, " ", name, 1, element=element)
    return atom


def _residue(resname: str, atoms: list[Atom.Atom]) -> Residue.Residue:
    residue = Residue.Residue((" ", 1, " "), resname, "")
    for atom in atoms:
        residue.add(atom)
    return residue


def test_count_cross_contacts_finds_close_atoms():
    res_a = _residue(
        "ALA",
        [
            _atom("CA", (0.0, 0.0, 0.0)),
            _atom("CB", (1.0, 0.0, 0.0)),
        ],
    )
    res_b = _residue("GLY", [_atom("CA", (10.0, 0.0, 0.0))])
    res_c = _residue("GLY", [_atom("CA", (1.5, 0.0, 0.0))])

    close = count_cross_contacts(heavy_atoms(res_a), heavy_atoms(res_c), cutoff=4.5)
    far = count_cross_contacts(heavy_atoms(res_a), heavy_atoms(res_b), cutoff=4.5)
    assert close > 0
    assert far == 0


def test_contact_analyzer_matches_spatial_helper():
    res_a = _residue("ALA", [_atom("CA", (0.0, 0.0, 0.0)), _atom("CB", (1.0, 0.0, 0.0))])
    res_b = _residue("GLY", [_atom("CA", (1.4, 0.0, 0.0))])
    analyzer = ContactAnalyzer(cutoff=4.5)
    assert analyzer.count_contacts(res_a, [res_b]) == count_cross_contacts(
        heavy_atoms(res_a), heavy_atoms(res_b), 4.5
    )


def test_min_inter_atomic_distance():
    res_a = _residue("ALA", [_atom("CA", (0.0, 0.0, 0.0))])
    res_b = _residue("GLY", [_atom("CA", (3.0, 0.0, 0.0))])
    assert min_inter_atomic_distance(heavy_atoms(res_a), heavy_atoms(res_b)) == 3.0
