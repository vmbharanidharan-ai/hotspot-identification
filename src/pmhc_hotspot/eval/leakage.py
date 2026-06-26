"""Dataset leakage checks for gatekeeper."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Set

from pmhc_hotspot.benchmark.stcrdab import default_eval_pdb_ids
from pmhc_hotspot.schema.examples import ComplexExample


def load_holdout_pdb_ids() -> Set[str]:
    return {p.upper() for p in default_eval_pdb_ids()}


def pdb_ids_in_train_split(processed_dir: Path) -> Set[str]:
    train_dir = processed_dir / "examples" / "train"
    if not train_dir.exists():
        return set()
    ids: set[str] = set()
    for path in train_dir.glob("*.json"):
        example = ComplexExample.model_validate(json.loads(path.read_text()))
        ids.add(example.provenance.pdb_id.upper())
    return ids


def pdb_ids_from_stcrdab_manifest(manifest_path: Path) -> Set[str]:
    if not manifest_path.exists():
        return set()
    payload = json.loads(manifest_path.read_text())
    stcrdab = payload.get("stcrdab") or {}
    return {str(p).upper() for p in stcrdab.get("included_pdb_ids", [])}


def find_eval_leakage(
    processed_dir: Path,
    dataset_manifest: Path | None = None,
) -> list[str]:
    """
    Return eval PDB IDs present in the training split or STCRDab ingest.

    Holdout examples under examples/holdout/ are expected and not counted as leakage.
    """
    holdout = load_holdout_pdb_ids()
    train_ids = pdb_ids_in_train_split(processed_dir)
    leaked = sorted(holdout & train_ids)

    if dataset_manifest is not None:
        stcrdab_ids = pdb_ids_from_stcrdab_manifest(dataset_manifest)
        leaked = sorted(set(leaked) | (holdout & stcrdab_ids))

    return leaked
