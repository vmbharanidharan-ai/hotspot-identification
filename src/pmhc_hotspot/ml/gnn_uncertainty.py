"""GNN uncertainty head (Phase 3.6)."""

from __future__ import annotations


def build_hotspot_gnn_with_uncertainty(input_dim: int, hidden_dim: int = 64, num_layers: int = 3, dropout: float = 0.2):
    torch, nn, SAGEConv = _require_pyg()
    from pmhc_hotspot.ml.gnn_model import build_hotspot_gnn

    base = build_hotspot_gnn(input_dim, hidden_dim=hidden_dim, num_layers=num_layers, dropout=dropout)

    class HotspotGNNWithUncertainty(base.__class__):
        def __init__(self):
            super().__init__()
            self.uncertainty_head = nn.Sequential(
                nn.Linear(hidden_dim, 32),
                nn.ReLU(),
                nn.Linear(32, 1),
                nn.Softplus(),
            )

        def forward_with_uncertainty(self, x, edge_index, batch=None):
            h = x
            for conv in self.convs:
                h = conv(h, edge_index)
                h = torch.relu(h)
                h = self.dropout(h)
            mu = self.classifier(h).squeeze(-1)
            sigma = self.uncertainty_head(h).squeeze(-1)
            return mu, sigma

    return HotspotGNNWithUncertainty()


def calibrated_loss(mu, sigma, y):
    torch = __import__("torch")
    nll = -torch.log(sigma + 1e-6) - 0.5 * ((y - torch.sigmoid(mu)) / (sigma + 1e-6)) ** 2
    return -nll.mean()


def _require_pyg():
    try:
        import torch
        import torch.nn as nn
        from torch_geometric.nn import SAGEConv
    except ImportError as exc:
        raise ImportError('Install torch-geometric') from exc
    return torch, nn, SAGEConv
