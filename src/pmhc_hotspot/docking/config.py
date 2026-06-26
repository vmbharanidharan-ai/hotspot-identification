"""Docking prior configuration (M3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

import yaml


@dataclass
class DockingPriorConfig:
    enabled: bool = True
    method: str = "geometry_consensus"
    ensemble_size: int = 1
    weights: Dict[str, float] = field(
        default_factory=lambda: {
            "relative_sasa": 0.35,
            "protrusion": 0.25,
            "bulge": 0.20,
            "tcr_exposure_prior": 0.15,
            "chemical_norm": 0.05,
        }
    )
    output_dir: Path = Path("artifacts/docking_priors")

    @classmethod
    def from_yaml(cls, path: str | Path) -> "DockingPriorConfig":
        with Path(path).open() as fh:
            data = yaml.safe_load(fh) or {}
        weights = data.get("weights") or cls().weights
        return cls(
            enabled=bool(data.get("enabled", True)),
            method=str(data.get("method", "geometry_consensus")),
            ensemble_size=int(data.get("ensemble_size", 1)),
            weights={str(k): float(v) for k, v in weights.items()},
            output_dir=Path(data.get("output_dir", "artifacts/docking_priors")),
        )
