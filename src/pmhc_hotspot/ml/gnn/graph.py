"""Peptide residue graph construction for GNN training."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
import pandas as pd

from pmhc_hotspot.ml.train import CATEGORICAL_COLUMNS, FEATURE_COLUMNS

GNN_NUMERIC_COLUMNS = [c for c in FEATURE_COLUMNS if c != "peptide_length"]
AA_ORDER = list("ACDEFGHIKLMNPQRSTVWY")
AA_TO_INDEX = {aa: i for i, aa in enumerate(AA_ORDER)}


@dataclass
class PeptideGraph:
    x: "torch.Tensor"
    edge_index: "torch.Tensor"
    y: "torch.Tensor"
    indices: np.ndarray
    pdb_id: str


def _require_torch():
    try:
        import torch
    except ImportError as exc:
        raise ImportError('Install the GNN extra: pip install -e ".[gnn]"') from exc
    return torch


def _position_sort_key(position: str, fallback: int) -> int:
    if isinstance(position, str) and position.startswith("P") and position[1:].isdigit():
        return int(position[1:]) - 1
    return fallback


def _node_features(group: pd.DataFrame) -> np.ndarray:
    rows = []
    for _, row in group.iterrows():
        numeric = [float(row.get(col, 0.0) or 0.0) for col in GNN_NUMERIC_COLUMNS]
        aa = str(row.get("aa", "X"))
        one_hot = [0.0] * len(AA_ORDER)
        if aa in AA_TO_INDEX:
            one_hot[AA_TO_INDEX[aa]] = 1.0
        rows.append(numeric + one_hot)
    return np.asarray(rows, dtype=np.float32)


def _sequential_edges(num_nodes: int) -> np.ndarray:
    if num_nodes < 2:
        return np.zeros((2, 0), dtype=np.int64)
    src: list[int] = []
    dst: list[int] = []
    for i in range(num_nodes - 1):
        src.extend([i, i + 1])
        dst.extend([i + 1, i])
    loops = np.arange(num_nodes, dtype=np.int64)
    src.extend(loops.tolist())
    dst.extend(loops.tolist())
    return np.asarray([src, dst], dtype=np.int64)


def build_graphs_from_dataframe(df: pd.DataFrame) -> Tuple[List[PeptideGraph], np.ndarray]:
    """Build one peptide graph per PDB from a residue-level training frame."""
    torch = _require_torch()
    graphs: list[PeptideGraph] = []
    all_indices: list[int] = []

    if "pdb_id" not in df.columns:
        raise ValueError("Training frame must include pdb_id for grouped GNN CV")

    for pdb_id, group in df.groupby("pdb_id", sort=True):
        group = group.copy()
        if "position_index" in group.columns:
            group["_sort"] = group["position_index"].astype(int)
        else:
            group["_sort"] = [
                _position_sort_key(pos, i) for i, pos in enumerate(group.get("position", []))
            ]
        group = group.sort_values("_sort")
        features = _node_features(group)
        edge_index = _sequential_edges(len(group))
        labels = group["label"].astype(int).to_numpy()
        indices = group.index.to_numpy()

        graphs.append(
            PeptideGraph(
                x=torch.tensor(features, dtype=torch.float32),
                edge_index=torch.tensor(edge_index, dtype=torch.long),
                y=torch.tensor(labels, dtype=torch.float32),
                indices=indices,
                pdb_id=str(pdb_id),
            )
        )
        all_indices.extend(indices.tolist())

    return graphs, np.asarray(all_indices, dtype=np.int64)


def graph_groups(df: pd.DataFrame) -> pd.Series:
    return df["pdb_id"].astype(str)
