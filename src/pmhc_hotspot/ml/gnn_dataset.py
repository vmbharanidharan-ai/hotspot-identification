"""PyG dataset for GNN training (Phase 3.1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

from pmhc_hotspot.ml.gnn_features import assemble_graph_inputs


def _require_pyg():
    try:
        from torch_geometric.data import Data
    except ImportError as exc:
        raise ImportError('Install torch-geometric: pip install -e ".[gnn]"') from exc
    return Data


class GNNTrainingDataset:
    """Build graphs from training frame or label JSON directory."""

    def __init__(self, items: List[dict]):
        self.items = items
        self.graphs = []
        for item in items:
            graph = assemble_graph_inputs(
                item["pdb_path"],
                item["peptide_chain"],
                item.get("allele"),
                item["labels"],
            )
            graph.pdb_id = item.get("pdb_id")
            self.graphs.append(graph)

    def __len__(self) -> int:
        return len(self.graphs)

    def __getitem__(self, idx: int):
        return self.graphs[idx]

    @classmethod
    def from_training_frame(cls, df: pd.DataFrame, pdb_dir: Path) -> "GNNTrainingDataset":
        items = []
        for pdb_id, group in df.groupby("pdb_id"):
            labels = [int(v) for v in group.sort_values("position_index")["label"]]
            pep_chain = group.iloc[0].get("peptide_chain", "P")
            items.append(
                {
                    "pdb_id": pdb_id,
                    "pdb_path": str(pdb_dir / f"{pdb_id}.pdb"),
                    "peptide_chain": pep_chain,
                    "allele": group.iloc[0].get("allele"),
                    "labels": labels,
                }
            )
        return cls(items)

    @classmethod
    def from_label_dir(cls, label_dir: Path, pdb_dir: Path) -> "GNNTrainingDataset":
        items = []
        for path in sorted(label_dir.glob("labels_*.json")):
            payload = json.loads(path.read_text())
            pdb_id = payload["pdb_id"]
            labels = [
                int(row["is_tcr_contact"])
                for _, row in sorted(
                    payload["residues"].items(),
                    key=lambda kv: kv[1]["position_index"],
                )
            ]
            items.append(
                {
                    "pdb_id": pdb_id,
                    "pdb_path": str(pdb_dir / f"{pdb_id}.pdb"),
                    "peptide_chain": payload["peptide_chain"],
                    "allele": None,
                    "labels": labels,
                }
            )
        return cls(items)


def stratified_split(dataset: GNNTrainingDataset, train: float = 0.8, val: float = 0.1):
    n = len(dataset)
    n_train = int(n * train)
    n_val = int(n * val)
    train_ds = GNNTrainingDataset(dataset.items[:n_train])
    val_ds = GNNTrainingDataset(dataset.items[n_train : n_train + n_val])
    test_ds = GNNTrainingDataset(dataset.items[n_train + n_val :])
    return train_ds, val_ds, test_ds


def to_dataloader(dataset: GNNTrainingDataset, batch_size: int = 16, shuffle: bool = True):
    from torch_geometric.loader import DataLoader
    return DataLoader(dataset.graphs, batch_size=batch_size, shuffle=shuffle)
