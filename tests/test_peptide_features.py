"""Tests for peptide featurization."""

import pandas as pd

from pmhc_hotspot.data.peptide_features import (
    MAX_PEPTIDE_POSITIONS,
    POSITION_CATEGORICAL_COLUMNS,
    POSITION_FEATURE_COLUMNS,
    featurize_peptide_table,
    peptide_position_features,
)


def test_peptide_position_features_padding():
    feats = peptide_position_features("GILGFVFTL")
    assert feats["pos_1_aa"] == "G"
    assert feats["pos_9_aa"] == "L"
    assert feats["pos_10_aa"] == "PAD"
    assert feats["anchor_p2_aa"] == "I"
    assert feats["anchor_omega_aa"] == "L"


def test_featurize_peptide_table_includes_position_columns():
    df = pd.DataFrame(
        {
            "peptide": ["GILGFVFTL"],
            "allele": ["HLA-A*02:01"],
            "label": [1],
            "source": ["TEST"],
            "group_id": ["g1"],
        }
    )
    out = featurize_peptide_table(df)
    for col in POSITION_FEATURE_COLUMNS + POSITION_CATEGORICAL_COLUMNS:
        assert col in out.columns
    assert out["allele"].iloc[0] == "HLA-A*02:01"
    assert len([c for c in out.columns if c.startswith("pos_1_")]) >= 6


def test_position_feature_count_matches_max_length():
    assert len([c for c in POSITION_FEATURE_COLUMNS if c.startswith("pos_1_")]) == 5
    assert len(POSITION_CATEGORICAL_COLUMNS) == MAX_PEPTIDE_POSITIONS + 2
