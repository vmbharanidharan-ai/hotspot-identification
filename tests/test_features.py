"""Tests for allele rules."""

from pmhc_hotspot.features.allele_rules import (
    AnchorFilter,
    get_anchor_positions,
    normalize_allele,
)
from pmhc_hotspot.scoring.baseline import HotspotScorer


def test_normalize_allele():
    assert normalize_allele("HLA-A02:01") == "HLA-A*02:01"
    assert normalize_allele("HLA-A*02:01") == "HLA-A*02:01"


def test_anchor_positions_variable_length():
    anchors_9 = get_anchor_positions("HLA-A*02:01", 9)
    assert anchors_9 == frozenset({2, 9})
    anchors_10 = get_anchor_positions("HLA-A*02:01", 10)
    assert anchors_10 == frozenset({2, 10})


def test_anchor_suppression_buried_vs_exposed():
    filt = AnchorFilter("HLA-A*02:01")
    buried_penalty = filt.penalty(2, 9, buried=True, relative_sasa=0.1)
    exposed_penalty = filt.penalty(2, 9, buried=False, relative_sasa=0.8)
    assert buried_penalty > exposed_penalty


def test_scores_bounded():
    scorer = HotspotScorer("HLA-A*02:01")
    features = {
        "sasa": 0.9,
        "protrusion": 0.8,
        "curvature": 0.5,
        "bulge": 0.6,
        "mutation_proximity": 0.0,
        "hla_contact_norm": 0.2,
        "tcr_exposure_prior": 0.9,
        "chemical_norm": 0.7,
        "confidence": 0.95,
    }
    score, _ = scorer.score_residue(features, 5, 9, buried=False)
    assert 0.0 <= score <= 1.0
