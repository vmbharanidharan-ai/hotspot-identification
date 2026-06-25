"""Hybrid rule-based + ML scoring."""

from __future__ import annotations

import numpy as np


class HybridScorer:
    """
    Combine deterministic rule scores with ML probabilities.

    alpha weights the rule-based component; (1-alpha) weights ML.
    """

    def __init__(self, alpha: float = 0.5):
        if not 0.0 <= alpha <= 1.0:
            raise ValueError("alpha must be in [0, 1]")
        self.alpha = alpha

    def combine(self, rule_prob, ml_prob) -> np.ndarray:
        rule_prob = np.asarray(rule_prob, dtype=float)
        ml_prob = np.asarray(ml_prob, dtype=float)
        return self.alpha * rule_prob + (1.0 - self.alpha) * ml_prob
