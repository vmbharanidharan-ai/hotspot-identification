"""Save and load staged ML model bundles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib

PACKAGE_VERSION = "0.3.0"
DEFAULT_MODEL_FILENAME = "default_staged_xgb.joblib"


def bundled_models_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "models"


def default_model_path() -> Path:
    """Path to the shipped default model bundle (may not exist until promoted)."""
    return bundled_models_dir() / DEFAULT_MODEL_FILENAME


def resolve_model_bundle_path(
    path: str | Path | None = None,
    *,
    allow_missing: bool = False,
) -> Path | None:
    """
    Resolve a model bundle path in priority order:

    1. explicit ``path``
    2. ``PMHC_HOTSPOT_MODEL`` environment variable
    3. packaged default under ``pmhc_hotspot/models/``
    4. local CI champion at ``artifacts/models/staged_xgb.joblib``
    """
    import os

    candidates: list[Path] = []
    if path is not None:
        candidates.append(Path(path))
    env_path = os.environ.get("PMHC_HOTSPOT_MODEL")
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(default_model_path())
    candidates.append(Path("artifacts/models/staged_xgb.joblib"))

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    if allow_missing:
        return None
    searched = ", ".join(str(c) for c in candidates)
    raise FileNotFoundError(
        f"No model bundle found. Searched: {searched}. "
        "Train with `python scripts/train_once.py` or pass --ml-bundle."
    )


def resolve_default_model_bundle(*, allow_missing: bool = False) -> StagedModelBundle | None:
    """Load the default staged model bundle if available."""
    path = resolve_model_bundle_path(allow_missing=allow_missing)
    if path is None:
        return None
    return load_staged_bundle(path)


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
