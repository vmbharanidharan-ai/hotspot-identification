"""Peptide residue GNN prototype (M4)."""

from pmhc_hotspot.ml.gnn.compare import (
    build_training_frame_for_compare,
    compare_xgboost_gnn,
    run_baseline_compare,
)
from pmhc_hotspot.ml.gnn.config import BaselineCompareConfig, GNNTrainConfig
from pmhc_hotspot.ml.gnn.graph import PeptideGraph, build_graphs_from_dataframe
from pmhc_hotspot.ml.gnn.model import build_peptide_gcn
from pmhc_hotspot.ml.gnn.train import train_gnn_cv, train_gnn_cv_from_config

__all__ = [
    "BaselineCompareConfig",
    "GNNTrainConfig",
    "PeptideGraph",
    "build_graphs_from_dataframe",
    "build_peptide_gcn",
    "build_training_frame_for_compare",
    "compare_xgboost_gnn",
    "run_baseline_compare",
    "train_gnn_cv",
    "train_gnn_cv_from_config",
]
