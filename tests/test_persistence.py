"""Tests for staged model persistence."""

import joblib

from pmhc_hotspot.ml.persistence import StagedModelBundle, load_staged_bundle, save_staged_bundle


class _DummyModel:
    def predict_proba(self, X):
        import numpy as np

        n = len(X)
        return np.column_stack([np.zeros(n), np.ones(n) * 0.7])


def test_save_and_load_staged_bundle(tmp_path):
    bundle = StagedModelBundle(
        final_model=_DummyModel(),
        feature_columns=["sasa", "aa"],
        categorical_columns=["aa"],
        model_type="logistic",
        use_pretrain_feature=False,
        contact_mode="standard",
        hybrid_alpha=0.6,
    )
    path = tmp_path / "model.joblib"
    save_staged_bundle(path, bundle)
    loaded = load_staged_bundle(path)
    assert loaded.model_type == "logistic"
    assert loaded.contact_mode == "standard"
    assert loaded.feature_columns == ["sasa", "aa"]
    assert path.with_suffix(path.suffix + ".meta.json").exists()
    assert isinstance(joblib.load(path), StagedModelBundle)
