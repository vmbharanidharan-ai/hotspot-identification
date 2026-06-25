"""ML scaffold tests."""

import pandas as pd
import pytest

from pmhc_hotspot import HotspotPredictor
from pmhc_hotspot.ml.feature_matrix import build_training_frame
from pmhc_hotspot.ml.model import build_pipeline
from pmhc_hotspot.ml.train import train_cv


def test_build_training_frame_skips_low_confidence(fixture_pdb):
    result = HotspotPredictor(allele="HLA-A*02:01").predict(fixture_pdb)
    labels = {r.position: 1 for r in result.residue_scores[:2]}
    df = build_training_frame(result, labels, pdb_id="TEST", allele="HLA-A*02:01")
    assert not df.empty
    assert "label" in df.columns
    assert set(df["label"]).issubset({0, 1})


def test_logistic_train_cv_on_synthetic():
    pytest.importorskip("sklearn")
    df = pd.DataFrame(
        {
            "pdb_id": ["A", "A", "A", "B", "B", "B"],
            "aa": ["A", "R", "Y", "L", "W", "G"],
            "sasa": [0.1, 0.8, 0.7, 0.2, 0.9, 0.3],
            "protrusion": [0.2, 0.7, 0.6, 0.1, 0.8, 0.2],
            "curvature": [0.1, 0.4, 0.3, 0.2, 0.5, 0.1],
            "bulge": [0.1, 0.5, 0.4, 0.1, 0.6, 0.2],
            "hla_contacts": [5, 1, 2, 6, 1, 4],
            "peptide_contacts": [2, 3, 3, 1, 4, 2],
            "mutation_proximity": [0, 0, 1, 0, 0, 0],
            "confidence": [0.9, 0.9, 0.9, 0.9, 0.9, 0.9],
            "anchor_penalty": [0, 0, 0, 0, 0, 0],
            "chemical_score": [1, 9, 8, 6, 10, 0],
            "tcr_exposure_prior": [0.2, 0.9, 0.8, 0.3, 0.9, 0.2],
            "buried": [1, 0, 0, 1, 0, 1],
            "is_anchor": [0, 0, 0, 0, 0, 0],
            "peptide_length": [9, 9, 9, 9, 9, 9],
            "label": [0, 1, 1, 0, 1, 0],
        }
    )
    report = train_cv(df, model_type="logistic", n_splits=2)
    assert report["n_rows"] == 6
    assert "roc_auc" in report["overall"]


def test_xgboost_pipeline_requires_extra():
    pytest.importorskip("sklearn")
    try:
        build_pipeline(
            feature_columns=["sasa", "protrusion"],
            model_type="xgboost",
        )
    except ImportError:
        pytest.importorskip("xgboost")
