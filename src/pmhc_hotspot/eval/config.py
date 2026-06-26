"""Load design eval configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml

from pmhc_hotspot.schema.conditioning import ControlGroup


@dataclass
class EvalConfig:
    seed: int = 42
    primary_metric: str = "af2_ipae"
    higher_is_better: bool = False
    tolerance: float = 0.5
    min_improvement_fraction: float = 0.05
    control_groups: List[ControlGroup] = field(
        default_factory=lambda: [
            ControlGroup.random,
            ControlGroup.exposed_only,
            ControlGroup.central_only,
            ControlGroup.predicted,
        ]
    )
    reference_group: ControlGroup = ControlGroup.predicted
    inputs_dir: Path = Path("artifacts/design_inputs")
    outputs_dir: Path = Path("artifacts/design_outputs")
    metrics_dir: Path = Path("artifacts/metrics")
    stub_mode: bool = True

    @classmethod
    def from_yaml(cls, path: str | Path) -> "EvalConfig":
        with Path(path).open() as fh:
            data = yaml.safe_load(fh) or {}
        ranking = data.get("ranking") or {}
        groups = [ControlGroup(g) for g in data.get("control_groups", [g.value for g in cls().control_groups])]
        ref = data.get("reference_group", "predicted")
        af2 = bool(ranking.get("af2_multimer", False))
        mpnn = bool(ranking.get("proteinmpnn", False))
        rosetta = bool(ranking.get("rosetta", False))
        stub = not (af2 or mpnn or rosetta)
        return cls(
            seed=int(data.get("seed", 42)),
            primary_metric=str(data.get("primary_metric", "af2_ipae")),
            higher_is_better=bool(data.get("higher_is_better", False)),
            tolerance=float(data.get("tolerance", 0.5)),
            min_improvement_fraction=float(data.get("min_improvement_fraction", 0.05)),
            control_groups=groups,
            reference_group=ControlGroup(ref),
            inputs_dir=Path(data.get("inputs_dir", "artifacts/design_inputs")),
            outputs_dir=Path(data.get("outputs_dir", "artifacts/design_outputs")),
            metrics_dir=Path(data.get("metrics_dir", "artifacts/metrics")),
            stub_mode=stub,
        )
