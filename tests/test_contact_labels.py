"""Tests for tiered TCR-contact label definitions."""

from pmhc_hotspot.benchmark.contact_labels import residue_is_contact


def test_permissive_is_looser_than_strict():
    far_pair = [(5.2, True, True)]
    mid_pair = [(4.0, True, True)]
    close_pair = [(3.2, True, True)]
    backbone_pair = [(4.0, False, False)]

    assert not residue_is_contact(far_pair, "permissive")
    assert residue_is_contact(mid_pair, "permissive")
    assert residue_is_contact(backbone_pair, "permissive")

    assert not residue_is_contact(mid_pair, "strict")
    assert residue_is_contact(close_pair, "strict")

    assert residue_is_contact(mid_pair, "standard")
    assert not residue_is_contact(backbone_pair, "standard")
