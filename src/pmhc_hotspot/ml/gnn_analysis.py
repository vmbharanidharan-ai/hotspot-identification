"""GNN interpretability and feature importance (Phase 3.4)."""

from __future__ import annotations

from typing import Dict, List


def analyze_feature_importance(model, test_loader, feature_names: List[str]) -> Dict[str, float]:
    baseline = _eval_auc(model, test_loader)
    importance: dict[str, float] = {}
    for i, name in enumerate(feature_names):
        perturbed_auc = _eval_auc(model, test_loader, zero_feature_idx=i)
        importance[name] = max(0.0, baseline - perturbed_auc)
    return dict(sorted(importance.items(), key=lambda kv: -kv[1]))


def _eval_auc(model, loader, zero_feature_idx: int | None = None) -> float:
    torch = __import__("torch")
    from sklearn.metrics import roc_auc_score

    model.eval()
    preds, labels = [], []
    with torch.no_grad():
        for batch in loader:
            x = batch.x.clone()
            if zero_feature_idx is not None:
                x[:, zero_feature_idx] = 0.0
            logits = model(x, batch.edge_index, batch.batch)
            preds.extend(torch.sigmoid(logits).cpu().numpy())
            labels.extend(batch.y.cpu().numpy())
    if len(set(labels)) < 2:
        return 0.0
    return float(roc_auc_score(labels, preds))


def visualize_gnn_internals(model, test_structure, output_file: str) -> str:
    """Placeholder for embedding visualization."""
    with open(output_file, "w") as fh:
        fh.write("# GNN internal visualization placeholder\n")
    return output_file
