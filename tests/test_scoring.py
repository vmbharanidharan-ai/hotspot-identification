"""Tests for end-to-end scoring."""

from pmhc_hotspot import HotspotPredictor


def test_predict_returns_result(fixture_pdb):
    result = HotspotPredictor(allele="HLA-A*02:01").predict(fixture_pdb)
    assert result.peptide_length == 9
    assert len(result.residue_scores) == 9
    assert all(0.0 <= r.score <= 1.0 for r in result.residue_scores)
    assert len(result.hotspots) >= 3
    assert len(result.hotspots) <= 6
    assert result.rfdiffusion_hotspot_res


def test_skips_anchor_p2_when_buried(fixture_pdb):
    result = HotspotPredictor(allele="HLA-A*02:01").predict(fixture_pdb)
    hotspot_positions = {h.position for h in result.hotspots}
    # P2 is anchor; should generally not be selected
    assert "P2" not in hotspot_positions or all(
        not h.is_buried for h in result.hotspots if h.position == "P2"
    )


def test_mutation_soft_bias(fixture_pdb):
    base = HotspotPredictor(allele="HLA-A*02:01").predict(fixture_pdb)
    mut = HotspotPredictor(allele="HLA-A*02:01", mutation_positions=[4]).predict(fixture_pdb)
    p5_base = next(r for r in base.residue_scores if r.position == "P5")
    p5_mut = next(r for r in mut.residue_scores if r.position == "P5")
    assert p5_mut.mutation_proximity >= p5_base.mutation_proximity
