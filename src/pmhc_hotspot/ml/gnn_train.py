"""GNN training loop with early stopping (Phase 3.3)."""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np


def train_gnn(
    train_loader,
    val_loader,
    input_dim: int,
    *,
    epochs: int = 100,
    lr: float = 1e-3,
    hidden_dim: int = 64,
    num_layers: int = 3,
    patience: int = 10,
    checkpoint_path: str = "artifacts/models/gnn_best.pth",
) -> Any:
    torch, F = _require_torch()
    from sklearn.metrics import roc_auc_score

    from pmhc_hotspot.ml.gnn_model import build_hotspot_gnn

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_hotspot_gnn(input_dim, hidden_dim=hidden_dim, num_layers=num_layers).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    best_auc = 0.0
    patience_counter = 0
    for epoch in range(epochs):
        model.train()
        for batch in train_loader:
            batch = batch.to(device)
            optimizer.zero_grad()
            logits = model(batch.x, batch.edge_index, batch.batch)
            loss = F.binary_cross_entropy_with_logits(logits, batch.y.float())
            loss.backward()
            optimizer.step()

        model.eval()
        val_preds, val_labels = [], []
        with torch.no_grad():
            for batch in val_loader:
                batch = batch.to(device)
                logits = model(batch.x, batch.edge_index, batch.batch)
                val_preds.extend(torch.sigmoid(logits).cpu().numpy())
                val_labels.extend(batch.y.cpu().numpy())
        val_auc = roc_auc_score(val_labels, val_preds) if len(set(val_labels)) > 1 else 0.0
        if val_auc > best_auc:
            best_auc = val_auc
            patience_counter = 0
            torch.save(model.state_dict(), checkpoint_path)
        else:
            patience_counter += 1
            if patience_counter >= patience:
                break
    model.load_state_dict(torch.load(checkpoint_path, map_location=device))
    return model


def evaluate_gnn(model, test_loader, device: str = "cpu") -> Dict[str, float]:
    torch = _require_torch()[0]
    from sklearn.metrics import average_precision_score, roc_auc_score

    model.eval()
    preds, labels = [], []
    with torch.no_grad():
        for batch in test_loader:
            batch = batch.to(device)
            logits = model(batch.x, batch.edge_index, batch.batch)
            preds.extend(torch.sigmoid(logits).cpu().numpy())
            labels.extend(batch.y.cpu().numpy())
    y = np.array(labels)
    p = np.array(preds)
    return {
        "auc_roc": float(roc_auc_score(y, p)) if len(set(y)) > 1 else float("nan"),
        "avg_precision": float(average_precision_score(y, p)) if len(set(y)) > 1 else float("nan"),
    }


def _require_torch():
    try:
        import torch
        import torch.nn.functional as F
    except ImportError as exc:
        raise ImportError('Install torch: pip install -e ".[gnn]"') from exc
    return torch, F
