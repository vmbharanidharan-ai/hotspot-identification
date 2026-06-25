"""Tests for calibration and hybrid weight learning."""

import numpy as np
import pandas as pd

from pmhc_hotspot.ml.calibration import learn_hybrid_alpha


def test_learn_hybrid_alpha_prefers_better_component():
    y = pd.Series([0, 0, 1, 1, 0, 1])
    stat = pd.Series([0.1, 0.2, 0.8, 0.9, 0.15, 0.85])
    ml = pd.Series([0.9, 0.85, 0.2, 0.1, 0.8, 0.15])
    alpha_stat = learn_hybrid_alpha(stat, ml, y)
    alpha_ml = learn_hybrid_alpha(ml, stat, y)
    assert alpha_stat > alpha_ml
