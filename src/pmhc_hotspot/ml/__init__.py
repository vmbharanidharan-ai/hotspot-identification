"""Optional ML training and inference."""

from pmhc_hotspot.ml.feature_matrix import build_training_frame
from pmhc_hotspot.ml.hybrid import HybridScorer
from pmhc_hotspot.ml.model import build_base_estimator, build_pipeline
from pmhc_hotspot.ml.predict import predict_labels, predict_proba
from pmhc_hotspot.ml.pretrain import train_public_pretrain
from pmhc_hotspot.ml.staged import run_staged_training
from pmhc_hotspot.ml.train import train_cv

__all__ = [
    "HybridScorer",
    "build_base_estimator",
    "build_pipeline",
    "build_training_frame",
    "predict_labels",
    "predict_proba",
    "run_staged_training",
    "train_cv",
    "train_public_pretrain",
]
