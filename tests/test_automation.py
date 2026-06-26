"""Tests for automation gates and default model resolution."""

import json

import pytest

from pmhc_hotspot.automation.biology_gate import run_biology_gate
from pmhc_hotspot.automation.metrics_gate import compare_metrics, load_baseline_metrics
from pmhc_hotspot.ml.persistence import (
    StagedModelBundle,
    default_model_path,
    resolve_model_bundle_path,
    save_staged_bundle,
)


class _DummyModel:
    def predict_proba(self, X):
        import numpy as np

        n = len(X)
        return np.column_stack([np.zeros(n), np.ones(n) * 0.7])


def test_compare_metrics_passes_strong_candidate():
    baseline = load_baseline_metrics()
    training = {
        "finetune_cv": {"overall": {"roc_auc": 0.90}},
        "statistical_cv": {"overall": {"roc_auc": 0.85}},
        "pretrain_cv": {"roc_auc": 0.75},
    }
    benchmark = {
        "scoring_mode": "hybrid",
        "summary": {
            "mean_recall_at_5": 0.80,
            "mean_buried_anchor_avoidance_at_5": 0.95,
            "mean_anchor_avoidance_at_5": 0.90,
        },
    }
    result = compare_metrics(
        training_report=training,
        benchmark_report=benchmark,
        baseline=baseline,
    )
    assert result["passed"] is True


def test_compare_metrics_fails_regression():
    training = {"finetune_cv": {"overall": {"roc_auc": 0.50}}}
    benchmark = {"scoring_mode": "hybrid", "summary": {"mean_recall_at_5": 0.10}}
    baseline = {
        "training": {"finetune_roc_auc": 0.85},
        "benchmark": {"hybrid": {"mean_recall_at_5": 0.70}},
    }
    result = compare_metrics(
        training_report=training,
        benchmark_report=benchmark,
        baseline=baseline,
    )
    assert result["passed"] is False


def test_biology_gate_fails_low_buried_anchor_avoidance():
    report = {
        "summary": {
            "mean_buried_anchor_avoidance_at_5": 0.50,
            "mean_anchor_avoidance_at_5": 0.90,
            "n_structures": 1,
        },
        "results": [
            {
                "pdb_id": "TEST",
                "skipped": False,
                "buried_anchor_avoidance_at_k": {5: 0.50},
                "anchor_avoidance_at_k": {5: 0.90},
            }
        ],
    }
    result = run_biology_gate(report, min_buried_anchor_avoidance=0.85)
    assert result["passed"] is False
    assert result["violations"]


def test_biology_gate_passes_plausible_predictions():
    report = {
        "summary": {
            "mean_buried_anchor_avoidance_at_5": 0.95,
            "mean_anchor_avoidance_at_5": 0.90,
            "n_structures": 2,
        },
        "results": [],
    }
    result = run_biology_gate(report)
    assert result["passed"] is True


def test_resolve_model_bundle_path_explicit(tmp_path):
    bundle = StagedModelBundle(
        final_model=_DummyModel(),
        feature_columns=["sasa"],
        categorical_columns=[],
        model_type="logistic",
        use_pretrain_feature=False,
    )
    path = tmp_path / "custom.joblib"
    save_staged_bundle(path, bundle)
    assert resolve_model_bundle_path(path) == path


def test_resolve_model_bundle_path_packaged_default(tmp_path, monkeypatch):
    bundle = StagedModelBundle(
        final_model=_DummyModel(),
        feature_columns=["sasa"],
        categorical_columns=[],
        model_type="logistic",
        use_pretrain_feature=False,
    )
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    target = model_dir / "default_staged_xgb.joblib"
    save_staged_bundle(target, bundle)

    monkeypatch.setattr(
        "pmhc_hotspot.ml.persistence.default_model_path",
        lambda: target,
    )
    assert resolve_model_bundle_path(allow_missing=False) == target


def test_resolve_model_bundle_missing_raises():
    with pytest.raises(FileNotFoundError):
        resolve_model_bundle_path("/nonexistent/model.joblib", allow_missing=False)
