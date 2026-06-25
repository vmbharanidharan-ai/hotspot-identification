"""Tests for RFdiffusion hotspot selection."""

from pmhc_hotspot.scoring.selection import select_rfdiffusion_hotspots
from pmhc_hotspot.types import ResidueScore


def _residue(position_index: int, aa: str, score: float, tcr_prior: float = 0.9) -> ResidueScore:
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
        relative_sasa=0.5,
        protrusion=1.0,
        curvature=0.5,
        bulge=0.5,
        hla_contacts=2,
        peptide_contacts=1,
        mutation_proximity=0.0,
        confidence=0.9,
        anchor_penalty=0.0,
        chemical_score=5.0,
        tcr_exposure_prior=tcr_prior,
        is_anchor=False,
        is_buried=False,
        low_confidence=False,
        eligible_for_hotspot=True,
        explanation="test",
    )


def test_selects_three_to_six_when_only_four_candidates():
    residues = [
        _residue(0, "A", 0.2, tcr_prior=0.2),
        _residue(1, "G", 0.1, tcr_prior=0.2),
        _residue(2, "L", 0.95),
        _residue(3, "V", 0.90),
        _residue(4, "F", 0.85),
        _residue(5, "T", 0.80),
        _residue(6, "Y", 0.75),
        _residue(7, "K", 0.70),
        _residue(8, "M", 0.65),
    ]
    hotspots = select_rfdiffusion_hotspots(residues, allele="HLA-A*02:01")
    assert 3 <= len(hotspots) <= 6


def test_accepts_polar_peptide_without_hydrophobic_failure():
    residues = [
        _residue(0, "A", 0.2, tcr_prior=0.2),
        _residue(1, "G", 0.1, tcr_prior=0.2),
        _residue(2, "S", 0.95),
        _residue(3, "T", 0.90),
        _residue(4, "N", 0.85),
        _residue(5, "Q", 0.80),
        _residue(6, "K", 0.75),
        _residue(7, "R", 0.70),
        _residue(8, "D", 0.65),
    ]
    hotspots = select_rfdiffusion_hotspots(residues, allele="HLA-A*02:01", min_hydrophobic=3)
    assert 3 <= len(hotspots) <= 6
