"""Batch enrichment of ComplexExample JSON with residue features."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from pmhc_hotspot.features.config import FeatureComputeConfig
from pmhc_hotspot.features.from_structure import enrich_example
from pmhc_hotspot.schema.examples import ComplexExample

logger = logging.getLogger(__name__)


@dataclass
class FeatureEnrichReport:
    enriched: list[str] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"enriched": self.enriched, "skipped": self.skipped}


def discover_examples(glob_pattern: str, *, repo_root: Path | None = None) -> list[Path]:
    root = repo_root or Path.cwd()
    pattern = Path(glob_pattern)
    search_root = pattern.parent if pattern.is_absolute() else root / pattern.parent
    name = pattern.name
    return sorted(p for p in search_root.glob(name) if p.is_file())


def load_example(path: Path) -> ComplexExample:
    return ComplexExample.model_validate(json.loads(path.read_text()))


def write_example(example: ComplexExample, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(example.model_dump(mode="json"), indent=2))


def enrich_examples(
    config: FeatureComputeConfig,
    paths: Optional[Iterable[Path]] = None,
    *,
    repo_root: Path | None = None,
) -> FeatureEnrichReport:
    """Attach ResidueFeatures to example JSON files."""
    repo_root = repo_root or Path.cwd()
    report = FeatureEnrichReport()
    example_paths = list(paths) if paths is not None else discover_examples(
        config.examples_glob, repo_root=repo_root
    )

    for path in example_paths:
        try:
            example = load_example(path)
            enriched = enrich_example(
                example,
                scoring_mode=config.scoring_mode,
                model_bundle=config.model_bundle,
                repo_root=repo_root,
            )
            if config.in_place:
                out_path = path
            else:
                rel = path.name
                for part in ("train", "holdout", "val", "test"):
                    if part in path.parts:
                        rel = f"{part}/{path.name}"
                        break
                out_path = config.output_dir / rel
            write_example(enriched, out_path)
            report.enriched.append(enriched.example_id)
        except Exception as exc:
            logger.warning("Skipping %s: %s", path, exc)
            report.skipped.append({"path": str(path), "error": str(exc)})

    report_path = config.output_dir / "feature_enrich_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report.to_dict(), indent=2))
    return report
