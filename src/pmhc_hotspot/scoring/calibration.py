"""Score normalization utilities."""

from __future__ import annotations


def minmax_normalize(values: list[float]) -> list[float]:
    """Min-max normalize to [0, 1]; constant vectors -> 0.5."""
    if not values:
        return []
    vmin, vmax = min(values), max(values)
    if vmax == vmin:
        return [0.5 for _ in values]
    return [(v - vmin) / (vmax - vmin) for v in values]
