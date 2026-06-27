"""GraphSAGE hotspot GNN (Phase 3.3)."""

from __future__ import annotations


def _require_torch_geometric():
    try:
        import torch
        import torch.nn as nn
        from torch_geometric.nn import SAGEConv
    except ImportError as exc:
        raise ImportError('Install: pip install -e ".[gnn]" torch-geometric') from exc
    return torch, nn, SAGEConv


def build_hotspot_gnn(input_dim: int, hidden_dim: int = 64, num_layers: int = 3, dropout: float = 0.2):
    torch, nn, SAGEConv = _require_torch_geometric()

    class HotspotGNN(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.convs = nn.ModuleList()
            dims = [input_dim] + [hidden_dim] * num_layers
            for i in range(len(dims) - 1):
                self.convs.append(SAGEConv(dims[i], dims[i + 1]))
            self.classifier = nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim // 2, 1),
            )
            self.dropout = nn.Dropout(dropout)

        def forward(self, x, edge_index, batch=None):
            h = x
            for conv in self.convs:
                h = conv(h, edge_index)
                h = torch.relu(h)
                h = self.dropout(h)
            return self.classifier(h).squeeze(-1)

    return HotspotGNN()


class HotspotGATGNN:
    """Placeholder for Graph Attention variant."""

    pass
