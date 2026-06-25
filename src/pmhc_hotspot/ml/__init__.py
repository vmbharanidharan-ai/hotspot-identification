"""ML training and inference scaffold (optional extra)."""

from pmhc_hotspot.ml.feature_matrix import build_training_frame
from pmhc_hotspot.ml.model import build_pipeline
from pmhc_hotspot.ml.predict import predict_labels, predict_proba
from pmhc_hotspot.ml.train import train_cv

__all__ = [
    "build_pipeline",
    "build_training_frame",
    "predict_labels",
    "predict_proba",
    "train_cv",
]
