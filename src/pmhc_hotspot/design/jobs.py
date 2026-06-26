"""RFdiffusion job manifests for HPC submission (M5 extension)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml

from pmhc_hotspot.schema.conditioning import ControlGroup, DesignConditioning


@dataclass
class JobManifestReport:
    written: list[str] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"written": self.written, "skipped": self.skipped}


def _load_conditioning(path: Path) -> DesignConditioning:
    with path.open() as fh:
        return DesignConditioning.model_validate(yaml.safe_load(fh) or {})


def build_rfdiffusion_job(
    conditioning: DesignConditioning,
    *,
    structure_path: str | None = None,
) -> dict:
    rfd = conditioning.rfdiffusion or {}
    return {
        "schema_version": "1.0",
        "target_id": conditioning.target_id,
        "control_group": conditioning.control_group.value,
        "pdb_id": conditioning.pdb_id,
        "structure_path": structure_path,
        "hotspot_res": rfd.get("hotspot_res", ""),
        "contigs": rfd.get("contigs", ""),
        "num_designs": int(rfd.get("num_designs", 100)),
        "seed": int(rfd.get("seed", 42)),
        "status": "pending",
        "backend": "rfdiffusion",
    }


def write_target_job_manifest(
    target_dir: Path,
    *,
    structure_path: str | None = None,
) -> Path:
    jobs: list[dict] = []
    for path in sorted(target_dir.glob("*.yaml")):
        conditioning = _load_conditioning(path)
        jobs.append(
            build_rfdiffusion_job(
                conditioning,
                structure_path=structure_path,
            )
        )
    out = target_dir / "rfdiffusion_jobs.json"
    out.write_text(json.dumps({"jobs": jobs}, indent=2))
    return out


def export_job_manifests(
    inputs_dir: Path,
    *,
    examples_by_target: dict[str, str] | None = None,
) -> JobManifestReport:
    """Write rfdiffusion_jobs.json per target under design_inputs."""
    report = JobManifestReport()
    if not inputs_dir.exists():
        return report

    examples_by_target = examples_by_target or {}
    for target_dir in sorted(p for p in inputs_dir.iterdir() if p.is_dir()):
        try:
            structure_path = examples_by_target.get(target_dir.name)
            path = write_target_job_manifest(target_dir, structure_path=structure_path)
            report.written.append(str(path))
        except Exception as exc:
            report.skipped.append({"target_id": target_dir.name, "error": str(exc)})
    return report
