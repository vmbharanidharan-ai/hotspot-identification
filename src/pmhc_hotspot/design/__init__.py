"""Design-conditioning export and control generation (M5)."""

from __future__ import annotations

from pathlib import Path

from pmhc_hotspot.schema.conditioning import ControlGroup, DesignConditioning


def conditioning_output_path(
    output_dir: Path,
    target_id: str,
    control_group: ControlGroup,
) -> Path:
    return output_dir / target_id / f"{control_group.value}.yaml"


def write_conditioning(conditioning: DesignConditioning, path: Path) -> Path:
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = conditioning.model_dump(mode="json")
    with path.open("w") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False)
    return path
