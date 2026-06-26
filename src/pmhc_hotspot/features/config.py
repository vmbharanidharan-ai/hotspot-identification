"""Load feature enrichment configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class FeatureComputeConfig:
    seed: int = 42
    examples_glob: str = "data/processed/examples/**/*.json"
    in_place: bool = True
    output_dir: Path = Path("artifacts/features")
    scoring_mode: str = "deterministic"
    model_bundle: Optional[Path] = None
    docking_prior: bool = False
    docking_config: Path = Path("configs/docking.yaml")

    @classmethod
    def from_yaml(cls, path: str | Path) -> "FeatureComputeConfig":
        with Path(path).open() as fh:
            data = yaml.safe_load(fh) or {}
        bundle = data.get("model_bundle")
        dock_cfg = data.get("docking_config", "configs/docking.yaml")
        return cls(
            seed=int(data.get("seed", 42)),
            examples_glob=str(data.get("examples_glob", "data/processed/examples/**/*.json")),
            in_place=bool(data.get("in_place", True)),
            output_dir=Path(data.get("output_dir", "artifacts/features")),
            scoring_mode=str(data.get("scoring_mode", "deterministic")),
            model_bundle=Path(bundle) if bundle else None,
            docking_prior=bool(data.get("docking_prior", False)),
            docking_config=Path(dock_cfg),
        )
