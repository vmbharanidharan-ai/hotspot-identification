"""Evaluation metrics for hotspot benchmarking."""

from __future__ import annotations


class HotspotEvaluator:
    """Compare predicted hotspots to structural ground truth."""

    @staticmethod
    def contact_recovery(
        predicted_positions: set[int],
        ground_truth_positions: set[int],
    ) -> float:
        """Recall: fraction of TCR-contacted positions recovered."""
        if not ground_truth_positions:
            return 0.0
        tp = len(predicted_positions & ground_truth_positions)
        return tp / len(ground_truth_positions)

    @staticmethod
    def anchor_avoidance(
        predicted_positions: set[int],
        anchor_positions: set[int],
    ) -> float:
        """Fraction of predictions that avoid anchor positions."""
        if not predicted_positions:
            return 0.0
        avoided = len(predicted_positions - anchor_positions)
        return avoided / len(predicted_positions)

    @staticmethod
    def patch_contiguity(selected_indices: list[int]) -> float:
        """Fraction of selected residues in the largest contiguous run."""
        if not selected_indices:
            return 0.0
        sorted_idx = sorted(selected_indices)
        best = current = 1
        for i in range(1, len(sorted_idx)):
            if sorted_idx[i] == sorted_idx[i - 1] + 1:
                current += 1
                best = max(best, current)
            else:
                current = 1
        return best / len(sorted_idx)
