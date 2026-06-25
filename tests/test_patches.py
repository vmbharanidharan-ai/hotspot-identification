"""Tests for patch selection."""

from pmhc_hotspot import HotspotPredictor
from pmhc_hotspot.scoring.patches import PatchSelector


def test_patches_contiguous(fixture_pdb):
    result = HotspotPredictor(allele="HLA-A*02:01").predict(fixture_pdb)
    for patch in result.patches:
        indices = [r.position_index for r in patch.residues]
        for i in range(1, len(indices)):
            assert indices[i] == indices[i - 1] + 1


def test_patch_selector_min_size():
    from pmhc_hotspot.types import ResidueScore

    scores = [
        ResidueScore("P", i + 1, position=f"P{i+1}", position_index=i, score=1.0 - i * 0.1)
        for i in range(5)
    ]
    patches = PatchSelector(min_patch_size=2, max_patches=2).select(scores)
    assert all(len(p.residues) >= 2 for p in patches)
