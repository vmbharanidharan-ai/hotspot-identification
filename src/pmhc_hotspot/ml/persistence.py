"""Save and load staged ML model bundles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib

PACKAGE_VERSION = "0.3.0"


@dataclass
class StagedModelBundle:
    """Artifacts from two-stage training used at inference."""

    final_model: Any
    feature_columns: list[str]
    categorical_columns: list[str]
    model_type: str
    use_pretrain_feature: bool
    contact_mode: str = "standard"
    pretrained_model: Any | None = None
    hybrid_alpha: float = 0.5
    package_version: str = PACKAGE_VERSION
    statistical_model: Any | None = None
    stat_feature_columns: list[str] | None = None
    use_stat_feature: bool = False
    calibrated: bool = True

    def to_metadata(self) -> dict:
        return {
            "model_type": self.model_type,
            "use_pretrain_feature": self.use_pretrain_feature,
            "use_stat_feature": self.use_stat_feature,
            "contact_mode": self.contact_mode,
            "feature_columns": self.feature_columns,
            "categorical_columns": self.categorical_columns,
            "stat_feature_columns": self.stat_feature_columns,
            "hybrid_alpha": self.hybrid_alpha,
            "package_version": self.package_version,
            "calibrated": self.calibrated,
            "has_pretrained_model": self.pretrained_model is not None,
            "has_statistical_model": self.statistical_model is not None,
        }


def save_staged_bundle(path: str | Path, bundle: StagedModelBundle) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path)
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    meta_path.write_text(json.dumps(bundle.to_metadata(), indent=2))
    return path


def load_staged_bundle(path: str | Path) -> StagedModelBundle:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Model bundle not found: {path}")
    bundle = joblib.load(path)
    if not isinstance(bundle, StagedModelBundle):
        raise TypeError(f"Expected StagedModelBundle at {path}, got {type(bundle)}")
    return bundle
