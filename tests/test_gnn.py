"""M4 GNN prototype tests."""

from __future__ import annotations

import pandas as pd
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("sklearn")
pytest.importorskip("xgboost")

from pmhc_hotspot.ml.gnn import (
    build_graphs_from_dataframe,
    build_peptide_gcn,
    compare_xgboost_gnn,
    train_gnn_cv,
)
from pmhc_hotspot.ml.gnn.config import BaselineCompareConfig


def _synthetic_training_frame() -> pd.DataFrame:
    rows = []
    for pdb_id, offset in [("A1", 0.0), ("B2", 0.15), ("C3", -0.1)]:
        for i in range(9):
            label = 1 if i in {3, 4, 5} else 0
            rows.append(
                {
                    "pdb_id": pdb_id,
                    "position": f"P{i + 1}",
                    "position_index": i,
                    "aa": "A" if label else "G",
                    "sasa": 0.2 + 0.08 * i + offset,
                    "hydrophobic_fraction": 0.3,
                    "polar_fraction": 0.2,
                    "protrusion": 0.1 + 0.07 * i + offset,
                    "curvature": 0.1 + 0.03 * i,
                    "bulge": 0.1 + 0.05 * i,
                    "hla_contacts": 2,
                    "peptide_contacts": 1,
                    "mutation_proximity": 0.0,
                    "confidence": 0.95,
                    "anchor_penalty": 0.0,
                    "chemical_score": 5.0,
                    "tcr_exposure_prior": 0.2 + 0.08 * i,
                    "buried": 0,
                    "is_anchor": 0,
                    "peptide_length": 9,
                    "label": label,
                }
            )
    return pd.DataFrame(rows)


def test_build_graphs_from_dataframe():
    df = _synthetic_training_frame()
    graphs, _ = build_graphs_from_dataframe(df)
    assert len(graphs) == 3
    assert graphs[0].x.shape[0] == 9
    assert graphs[0].edge_index.shape[0] == 2


def test_peptide_gcn_forward():
    df = _synthetic_training_frame()
    graphs, _ = build_graphs_from_dataframe(df)
    model = build_peptide_gcn(graphs[0].x.shape[1], hidden_dim=16, num_layers=2)
    logits = model(graphs[0].x, graphs[0].edge_index)
    assert logits.shape == (9,)


def test_train_gnn_cv_smoke():
    df = _synthetic_training_frame()
    report = train_gnn_cv(df, n_splits=3, epochs=20, hidden_dim=16, random_state=0)
    assert report["n_rows"] == len(df)
    assert "roc_auc" in report["overall"]


def test_compare_xgboost_gnn_smoke():
    df = _synthetic_training_frame()
    cfg = BaselineCompareConfig(n_splits=3, seed=0)
    cfg.gnn.epochs = 20
    cfg.gnn.hidden_dim = 16
    report = compare_xgboost_gnn(df, cfg)
    assert "comparison" in report
    assert "xgboost" in report and "gnn" in report
