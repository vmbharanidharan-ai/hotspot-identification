"""Load design export configuration from YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml

from pmhc_hotspot.schema.conditioning import ControlGroup


@dataclass
class DesignExportConfig:
    seed: int = 42
    scoring_mode: str = "hybrid"
    model_bundle: Optional[Path] = None
    output_dir: Path = Path("artifacts/design_inputs")
    examples_glob: str = "data/processed/examples/holdout/*.json"
    control_groups: List[ControlGroup] = field(
        default_factory=lambda: [
            ControlGroup.random,
            ControlGroup.exposed_only,
            ControlGroup.central_only,
            ControlGroup.predicted,
        ]
    )
    hotspot_count: int = 4
    rfdiffusion_num_designs: int = 100
    binder_length_min: int = 50
    binder_length_max: int = 80
    write_job_manifests: bool = True

    @classmethod
    def from_yaml(cls, path: str | Path) -> "DesignExportConfig":
        with Path(path).open() as fh:
            data = yaml.safe_load(fh) or {}
        rfd = data.get("rfdiffusion") or {}
        bundle = data.get("model_bundle")
        groups = [
            ControlGroup(g) for g in data.get("control_groups", [g.value for g in cls().control_groups])
        ]
        return cls(
            seed=int(data.get("seed", 42)),
            scoring_mode=str(data.get("scoring_mode", "hybrid")),
            model_bundle=Path(bundle) if bundle else None,
            output_dir=Path(data.get("output_dir", "artifacts/design_inputs")),
            examples_glob=str(
                data.get("examples_glob", "data/processed/examples/holdout/*.json")
            ),
            control_groups=groups,
            hotspot_count=int(data.get("hotspot_count", 4)),
            rfdiffusion_num_designs=int(rfd.get("num_designs", 100)),
            binder_length_min=int(rfd.get("binder_length_min", 50)),
            binder_length_max=int(rfd.get("binder_length_max", 80)),
            write_job_manifests=bool(data.get("write_job_manifests", True)),
        )
