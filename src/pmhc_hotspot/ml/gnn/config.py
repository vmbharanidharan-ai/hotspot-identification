"""Baseline / GNN training configuration (M4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass
class GNNTrainConfig:
    hidden_dim: int = 32
    num_layers: int = 2
    dropout: float = 0.1
    epochs: int = 120
    lr: float = 0.001
    weight_decay: float = 0.0001


@dataclass
class BaselineCompareConfig:
    seed: int = 42
    n_splits: int = 5
    contact_mode: str = "standard"
    cache_dir: Path = Path("data/pdb")
    download: bool = False
    holdout_manifest: Path = Path("src/pmhc_hotspot/benchmark/tcr_pmhc_manifest.yaml")
    training_manifest: Optional[Path] = None
    exclude_holdout_from_training: bool = True
    output_report: Path = Path("artifacts/reports/gnn_vs_xgboost.json")
    xgboost_model_type: str = "xgboost"
    gnn: GNNTrainConfig = field(default_factory=GNNTrainConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "BaselineCompareConfig":
        with Path(path).open() as fh:
            data = yaml.safe_load(fh) or {}
        gnn_data = data.get("gnn") or {}
        xgb = data.get("xgboost") or {}
        train_manifest = data.get("training_manifest")
        return cls(
            seed=int(data.get("seed", 42)),
            n_splits=int(data.get("n_splits", 5)),
            contact_mode=str(data.get("contact_mode", "standard")),
            cache_dir=Path(data.get("cache_dir", "data/pdb")),
            download=bool(data.get("download", False)),
            holdout_manifest=Path(
                data.get("holdout_manifest", "src/pmhc_hotspot/benchmark/tcr_pmhc_manifest.yaml")
            ),
            training_manifest=Path(train_manifest) if train_manifest else None,
            exclude_holdout_from_training=bool(data.get("exclude_holdout_from_training", True)),
            output_report=Path(data.get("output_report", "artifacts/reports/gnn_vs_xgboost.json")),
            xgboost_model_type=str(xgb.get("model_type", "xgboost")),
            gnn=GNNTrainConfig(
                hidden_dim=int(gnn_data.get("hidden_dim", 32)),
                num_layers=int(gnn_data.get("num_layers", 2)),
                dropout=float(gnn_data.get("dropout", 0.1)),
                epochs=int(gnn_data.get("epochs", 120)),
                lr=float(gnn_data.get("lr", 0.001)),
                weight_decay=float(gnn_data.get("weight_decay", 0.0001)),
            ),
        )

    def gnn_dict(self) -> Dict[str, Any]:
        return {
            "hidden_dim": self.gnn.hidden_dim,
            "num_layers": self.gnn.num_layers,
            "dropout": self.gnn.dropout,
            "epochs": self.gnn.epochs,
            "lr": self.gnn.lr,
            "weight_decay": self.gnn.weight_decay,
            "random_state": self.seed,
        }
