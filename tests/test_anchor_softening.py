"""Tests for soft anchor down-weighting in hotspot selection."""

from pmhc_hotspot.features.allele_rules import AnchorFilter
from pmhc_hotspot.scoring.selection import select_rfdiffusion_hotspots
from pmhc_hotspot.types import ResidueScore


def _residue(
    position_index: int,
    aa: str,
    score: float,
    *,
    is_anchor: bool = False,
    is_buried: bool = False,
    relative_sasa: float = 0.5,
    tcr_prior: float = 0.9,
) -> ResidueScore:
    return ResidueScore(
        chain_id="C",
        resseq=position_index + 1,
        icode="",
        aa=aa,
        position=f"P{position_index + 1}",
        position_index=position_index,
        normalized_position=position_index / 8,
        score=score,
        sasa=40.0,
        relative_sasa=relative_sasa,
        protrusion=1.0,
        curvature=0.5,
        bulge=0.5,
        hla_contacts=2,
        peptide_contacts=1,
        mutation_proximity=0.0,
        confidence=0.9,
        anchor_penalty=0.5 if is_anchor else 0.0,
        chemical_score=5.0,
        tcr_exposure_prior=tcr_prior,
        is_anchor=is_anchor,
        is_buried=is_buried,
        low_confidence=False,
        eligible_for_hotspot=True,
        explanation="test",
    )


def test_exposed_anchor_can_still_be_selected_when_top_scoring():
    residues = [
        _residue(0, "A", 0.2, tcr_prior=0.2),
        _residue(1, "L", 0.99, is_anchor=True, is_buried=False, relative_sasa=0.5),
        _residue(2, "V", 0.70),
        _residue(3, "F", 0.65),
        _residue(4, "T", 0.60),
        _residue(5, "Y", 0.55),
        _residue(6, "K", 0.50),
        _residue(7, "M", 0.45),
        _residue(8, "I", 0.40),
    ]
    hotspots = select_rfdiffusion_hotspots(residues, allele="HLA-A*02:01", max_hotspots=6)
    positions = {h.position for h in hotspots}
    assert "P2" in positions


def test_selection_multiplier_never_hard_zeros():
    anchor_filter = AnchorFilter("HLA-A*02:01")
    mult = anchor_filter.selection_multiplier(2, 9, buried=True, relative_sasa=0.1)
    assert 0.15 <= mult < 1.0
