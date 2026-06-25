"""Tests for public dataset loaders and staged ML."""

import pandas as pd
import pytest

from pmhc_hotspot.data.public_datasets import combine_public_datasets, load_atlas_csv, load_iedb_csv
from pmhc_hotspot.ml.hybrid import HybridScorer
from pmhc_hotspot.ml.pretrain import train_public_pretrain


def test_load_iedb_native_export():
    df = load_iedb_csv("tests/data/sample_iedb_native.csv")
    assert len(df) == 3
    assert set(df["label"]) == {0, 1}
    assert df["allele"].iloc[0].startswith("HLA-")


def test_combine_public_datasets():
    iedb = load_iedb_csv("tests/data/sample_iedb.csv")
    atlas = load_atlas_csv("tests/data/sample_atlas.csv")
    combined = combine_public_datasets([iedb, atlas])
    assert len(combined) >= 8
    assert "peptide_length" in combined.columns


def test_public_pretrain_cv():
    pytest.importorskip("sklearn")
    df = load_iedb_csv("tests/data/sample_iedb.csv")
    report = train_public_pretrain(df, model_type="logistic", n_splits=2)
    assert report["n_rows"] == 8
    assert "roc_auc" in report
    assert "disclaimer" in report


def test_hybrid_scorer():
    hs = HybridScorer(alpha=0.6)
    out = hs.combine([0.8, 0.2], [0.4, 0.9])
    assert out[0] == pytest.approx(0.6 * 0.8 + 0.4 * 0.4)


def test_fine_tune_with_pretrain_feature(fixture_pdb):
    pytest.importorskip("sklearn")
    from pmhc_hotspot import HotspotPredictor
    from pmhc_hotspot.ml.fine_tune import attach_pretrain_probabilities, fine_tune_structural
    from pmhc_hotspot.ml.pretrain import fit_public_pretrain_model

    public = load_iedb_csv("tests/data/sample_iedb.csv")
    pretrained, _ = fit_public_pretrain_model(public, model_type="logistic")

    result = HotspotPredictor(allele="HLA-A*02:01").predict(fixture_pdb)
    from pmhc_hotspot.ml.feature_matrix import build_training_frame

    labels = {r.position: int(i % 2) for i, r in enumerate(result.residue_scores)}
    structural = build_training_frame(
        result, labels, pdb_id="MINI", allele="HLA-A*02:01", peptide_length=9
    )
    structural = attach_pretrain_probabilities(structural, pretrained)
    assert "pretrain_prob" in structural.columns
    half = len(structural) // 2 or 1
    structural.loc[:half, "pdb_id"] = "A"
    structural.loc[half:, "pdb_id"] = "B"
    report = fine_tune_structural(structural, model_type="logistic", n_splits=2, use_pretrain_feature=True)
    assert report["use_pretrain_feature"] is True
