"""Load dataset build configuration from YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

import yaml


@dataclass
class DatasetBuildConfig:
    seed: int = 42
    raw_dir: Path = Path("data/raw")
    processed_dir: Path = Path("data/processed")
    cache_dir: Path = Path("data/pdb")
    sources: List[str] = field(default_factory=lambda: ["pdb_manifest"])
    stcrdab_path: Optional[Path] = None
    stcrdab_max_resolution: Optional[float] = 3.5
    stcrdab_exclude_eval: bool = True
    holdout_manifest: Path = Path("src/pmhc_hotspot/benchmark/tcr_pmhc_manifest.yaml")
    extra_manifests: List[Path] = field(default_factory=list)
    contact_mode: str = "standard"
    download: bool = True
    skip_missing: bool = True
    output_manifest: Path = Path("data/processed/dataset_manifest.json")

    @classmethod
    def from_yaml(cls, path: str | Path) -> "DatasetBuildConfig":
        with Path(path).open() as fh:
            data = yaml.safe_load(fh) or {}
        stcrdab = data.get("stcrdab") or {}
        splits = data.get("splits") or {}
        output = data.get("output") or {}
        st_path = stcrdab.get("path")
        return cls(
            seed=int(data.get("seed", 42)),
            raw_dir=Path(data.get("raw_dir", "data/raw")),
            processed_dir=Path(data.get("processed_dir", "data/processed")),
            cache_dir=Path(data.get("cache_dir", "data/pdb")),
            sources=list(data.get("sources", ["pdb_manifest"])),
            stcrdab_path=Path(st_path) if st_path else None,
            stcrdab_max_resolution=stcrdab.get("max_resolution"),
            stcrdab_exclude_eval=bool(stcrdab.get("exclude_eval_pdbs", True)),
            holdout_manifest=Path(
                splits.get("holdout_manifest", "src/pmhc_hotspot/benchmark/tcr_pmhc_manifest.yaml")
            ),
            contact_mode=str(data.get("contact_mode", "standard")),
            download=bool(data.get("download", True)),
            skip_missing=bool(data.get("skip_missing", True)),
            output_manifest=Path(output.get("manifest", "data/processed/dataset_manifest.json")),
        )
