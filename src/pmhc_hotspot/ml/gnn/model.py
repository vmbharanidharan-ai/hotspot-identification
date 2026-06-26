"""Lightweight peptide residue GCN (M4 prototype)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import torch
    from torch import nn


def _require_torch():
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise ImportError('Install the GNN extra: pip install -e ".[gnn]"') from exc
    return torch, nn


def build_peptide_gcn(
    in_dim: int,
    *,
    hidden_dim: int = 32,
    num_layers: int = 2,
    dropout: float = 0.1,
):
    torch, nn = _require_torch()

    class PeptideGCN(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            layers: list[nn.Module] = []
            dims = [in_dim] + [hidden_dim] * num_layers
            for i in range(len(dims) - 1):
                layers.append(nn.Linear(dims[i], dims[i + 1]))
            self.layers = nn.ModuleList(layers)
            self.head = nn.Linear(hidden_dim, 1)
            self.dropout = nn.Dropout(dropout)

        def _aggregate(self, h: "torch.Tensor", edge_index: "torch.Tensor") -> "torch.Tensor":
            src, dst = edge_index
            out = torch.zeros_like(h)
            out.index_add_(0, dst, h[src])
            degree = torch.bincount(dst, minlength=h.size(0)).float().clamp(min=1.0).unsqueeze(1)
            return out / degree

        def forward(self, x: "torch.Tensor", edge_index: "torch.Tensor") -> "torch.Tensor":
            h = x
            for i, layer in enumerate(self.layers):
                neighbor = self._aggregate(h, edge_index)
                h = layer(neighbor + (x if i == 0 else h))
                if i < len(self.layers) - 1:
                    h = torch.relu(h)
                    h = self.dropout(h)
            return self.head(h).squeeze(-1)

    return PeptideGCN()
