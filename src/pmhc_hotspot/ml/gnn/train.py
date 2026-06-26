"""Grouped cross-validation training for peptide GNN (M4)."""

from __future__ import annotations

import random
from typing import Any, Dict

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold, StratifiedKFold

from pmhc_hotspot.ml.gnn.graph import build_graphs_from_dataframe
from pmhc_hotspot.ml.gnn.model import build_peptide_gcn


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
    except ImportError:
        pass


def _train_graphs(model, graphs, *, epochs: int, lr: float, weight_decay: float):
    torch = __import__("torch")
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    criterion = torch.nn.BCEWithLogitsLoss()
    model.train()
    for _ in range(epochs):
        for graph in graphs:
            optimizer.zero_grad()
            logits = model(graph.x, graph.edge_index)
            loss = criterion(logits, graph.y)
            loss.backward()
            optimizer.step()


def _predict_graphs(model, graphs) -> Dict[int, float]:
    torch = __import__("torch")
    model.eval()
    preds: dict[int, float] = {}
    with torch.no_grad():
        for graph in graphs:
            logits = model(graph.x, graph.edge_index)
            probs = torch.sigmoid(logits).cpu().numpy()
            for idx, prob in zip(graph.indices, probs):
                preds[int(idx)] = float(prob)
    return preds


def train_gnn_cv(
    df: pd.DataFrame,
    *,
    n_splits: int = 5,
    random_state: int = 42,
    hidden_dim: int = 32,
    num_layers: int = 2,
    dropout: float = 0.1,
    epochs: int = 120,
    lr: float = 0.001,
    weight_decay: float = 0.0001,
) -> dict:
    """Grouped CV for peptide GNN vs the same residue labels as XGBoost."""
    graphs, _ = build_graphs_from_dataframe(df)
    if not graphs:
        raise ValueError("No graphs built from training frame")

    in_dim = int(graphs[0].x.shape[1])
    y = df["label"].astype(int)
    groups = df["pdb_id"].astype(str)

    if groups.nunique() >= n_splits:
        splitter = GroupKFold(n_splits=n_splits)
        split_iter = splitter.split(df, y, groups=groups)
    else:
        splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
        split_iter = splitter.split(df, y)

    graph_by_index = {int(idx): graph for graph in graphs for idx in graph.indices}
    oof = pd.Series(index=df.index, dtype=float)
    fold_metrics = []

    for fold, (train_idx, test_idx) in enumerate(split_iter, start=1):
        _set_seed(random_state + fold)
        train_graphs = []
        seen_pdb: set[str] = set()
        for idx in train_idx:
            graph = graph_by_index[int(idx)]
            if graph.pdb_id not in seen_pdb:
                train_graphs.append(graph)
                seen_pdb.add(graph.pdb_id)

        test_graphs = []
        seen_test: set[str] = set()
        for idx in test_idx:
            graph = graph_by_index[int(idx)]
            if graph.pdb_id not in seen_test:
                test_graphs.append(graph)
                seen_test.add(graph.pdb_id)

        model = build_peptide_gcn(
            in_dim,
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            dropout=dropout,
        )
        _train_graphs(
            model,
            train_graphs,
            epochs=epochs,
            lr=lr,
            weight_decay=weight_decay,
        )
        fold_preds = _predict_graphs(model, test_graphs)
        test_idx_set = {int(i) for i in test_idx}
        for idx, prob in fold_preds.items():
            if idx in test_idx_set:
                oof.loc[idx] = prob

        y_te = y.loc[test_idx]
        prob_te = oof.loc[test_idx]
        roc = roc_auc_score(y_te, prob_te) if len(set(y_te)) > 1 else float("nan")
        ap = average_precision_score(y_te, prob_te) if len(set(y_te)) > 1 else float("nan")
        fold_metrics.append({"fold": fold, "roc_auc": roc, "avg_precision": ap})

    overall = {
        "roc_auc": roc_auc_score(y, oof) if len(set(y)) > 1 else float("nan"),
        "avg_precision": average_precision_score(y, oof) if len(set(y)) > 1 else float("nan"),
    }
    return {
        "fold_metrics": fold_metrics,
        "overall": overall,
        "oof_predictions": oof.tolist(),
        "n_rows": len(df),
        "n_positive": int(y.sum()),
        "n_graphs": len(graphs),
        "model": "peptide_gcn",
    }


def train_gnn_cv_from_config(df: pd.DataFrame, config: Dict[str, Any]) -> dict:
    return train_gnn_cv(df, **config)
