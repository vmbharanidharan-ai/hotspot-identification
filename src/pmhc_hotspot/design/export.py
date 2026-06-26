"""Export four control-group design-conditioning YAML files per target (M5)."""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

from pmhc_hotspot.api import HotspotPredictor
from pmhc_hotspot.constants import DEFAULT_HOTSPOT_CONFIG, SKIP_ALWAYS
from pmhc_hotspot.design.config import DesignExportConfig
from pmhc_hotspot.export import build_contig_template
from pmhc_hotspot.io import StructureLoader, chain_ca_residues, get_chain
from pmhc_hotspot.schema.conditioning import (
    ControlGroup,
    DesignConditioning,
    HotspotEntry,
    PatchEntry,
)
from pmhc_hotspot.schema.examples import ComplexExample
from pmhc_hotspot.scoring.selection import select_rfdiffusion_hotspots
from pmhc_hotspot.types import HotspotPatch, ResidueScore

from pmhc_hotspot.design.io import conditioning_output_path, write_conditioning

logger = logging.getLogger(__name__)

_PATCH_LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


@dataclass
class DesignExportReport:
    exported: list[str] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"exported": self.exported, "skipped": self.skipped}


def load_examples(glob_pattern: str, *, repo_root: Path | None = None) -> list[ComplexExample]:
    root = repo_root or Path.cwd()
    pattern = Path(glob_pattern)
    if pattern.is_absolute():
        search_root = pattern.parent
        name = pattern.name
    else:
        search_root = root / pattern.parent
        name = pattern.name
    examples: list[ComplexExample] = []
    for path in sorted(search_root.glob(name)):
        if not path.is_file():
            continue
        payload = json.loads(path.read_text())
        examples.append(ComplexExample.model_validate(payload))
    return examples


def _eligible_residues(residue_scores: list[ResidueScore]) -> list[ResidueScore]:
    return [
        r
        for r in residue_scores
        if r.eligible_for_hotspot and r.aa not in SKIP_ALWAYS and not r.is_buried
    ]


def _pick_count(config: DesignExportConfig, eligible: list[ResidueScore]) -> int:
    cap = min(config.hotspot_count, DEFAULT_HOTSPOT_CONFIG["max_hotspots"])
    return min(cap, len(eligible)) if eligible else 0


def select_control_hotspots(
    control_group: ControlGroup,
    residue_scores: list[ResidueScore],
    *,
    allele: str | None,
    seed: int,
    hotspot_count: int,
) -> list[ResidueScore]:
    """Pick hotspot residues for a control group."""
    eligible = _eligible_residues(residue_scores)
    n = min(hotspot_count, len(eligible))
    if n == 0:
        return []

    if control_group == ControlGroup.predicted:
        return select_rfdiffusion_hotspots(
            residue_scores,
            allele=allele,
            max_hotspots=n,
            min_hotspots=min(3, n),
        )[:n]

    if control_group == ControlGroup.exposed_only:
        ranked = sorted(eligible, key=lambda r: (-r.relative_sasa, -r.score))
        return ranked[:n]

    if control_group == ControlGroup.central_only:
        central = [
            r
            for r in eligible
            if 3 <= r.position_index + 1 <= min(8, len(residue_scores))
        ]
        if not central:
            central = eligible
        ranked = sorted(central, key=lambda r: (-r.bulge, -r.score))
        return ranked[:n]

    rng = random.Random(seed)
    return rng.sample(eligible, n)


def _patch_entries(
    hotspots: list[ResidueScore],
    patches: list[HotspotPatch],
) -> tuple[list[HotspotEntry], list[PatchEntry]]:
    hotspot_entries: list[HotspotEntry] = []
    patch_by_residue: dict[int, str] = {}
    patch_entries: list[PatchEntry] = []

    for i, patch in enumerate(patches):
        patch_id = _PATCH_LABELS[i % len(_PATCH_LABELS)]
        members = [r.resseq for r in patch.residues]
        center = patch.residues[len(patch.residues) // 2].resseq
        for r in patch.residues:
            patch_by_residue[r.resseq] = patch_id
        patch_entries.append(
            PatchEntry(
                id=patch_id,
                center=center,
                radius=6.0,
                normal=[0.0, 0.0, 1.0],
                members=members,
                confidence=min(1.0, max(0.0, patch.patch_score)),
            )
        )

    for r in hotspots:
        confidence = min(1.0, max(0.0, r.score))
        hotspot_entries.append(
            HotspotEntry(
                residue=r.resseq,
                position=r.position,
                confidence=confidence,
                patch_id=patch_by_residue.get(r.resseq),
                chain=r.chain_id,
            )
        )

    return hotspot_entries, patch_entries


def _patches_from_hotspots(hotspots: list[ResidueScore]) -> list[HotspotPatch]:
    if not hotspots:
        return []
    ordered = sorted(hotspots, key=lambda r: r.position_index)
    mean_score = sum(r.score for r in ordered) / len(ordered)
    return [
        HotspotPatch(
            positions=[r.position for r in ordered],
            residues=ordered,
            patch_score=mean_score,
            patch_id=1,
        )
    ]


def build_conditioning(
    example: ComplexExample,
    prediction_residues: list[ResidueScore],
    patches: list[HotspotPatch],
    hotspots: list[ResidueScore],
    *,
    control_group: ControlGroup,
    config: DesignExportConfig,
    contig_template: str,
) -> DesignConditioning:
    hotspot_entries, patch_entries = _patch_entries(hotspots, patches)
    hotspot_res = ",".join(r.rfdiffusion_token for r in hotspots)
    return DesignConditioning(
        target_id=example.example_id,
        control_group=control_group,
        pdb_id=example.provenance.pdb_id,
        allele=example.allele,
        peptide={"chain": example.peptide_chain, "sequence": example.peptide_sequence},
        hla_chains=example.hla_chains,
        hotspots=hotspot_entries,
        patches=patch_entries,
        rfdiffusion={
            "hotspot_res": hotspot_res,
            "contigs": contig_template,
            "num_designs": config.rfdiffusion_num_designs,
            "seed": config.seed,
        },
        scoring_mode=config.scoring_mode,  # type: ignore[arg-type]
        model_bundle=str(config.model_bundle) if config.model_bundle else None,
    )


def export_target(
    example: ComplexExample,
    config: DesignExportConfig,
    *,
    repo_root: Path | None = None,
) -> list[Path]:
    """Write all control-group YAML files for one ComplexExample."""
    repo_root = repo_root or Path.cwd()
    structure_path = Path(example.structure_path)
    if not structure_path.is_absolute():
        structure_path = repo_root / structure_path
    if not structure_path.exists():
        raise FileNotFoundError(structure_path)

    predictor = HotspotPredictor(
        allele=example.allele,
        peptide_chain=example.peptide_chain,
        hla_chain=example.hla_chains[0] if example.hla_chains else None,
        scoring_mode=config.scoring_mode,
        ml_bundle=config.model_bundle,
    )
    result = predictor.predict(structure_path)
    n_hotspots = _pick_count(config, _eligible_residues(result.residue_scores))

    loader = StructureLoader()
    structure = loader.load(structure_path)
    pep_chain = get_chain(structure, result.peptide_chain_id)
    hla_chain = get_chain(structure, result.hla_chain_ids[0])
    pep_resseqs = [r.id[1] for r in chain_ca_residues(pep_chain)]
    hla_resseqs = [r.id[1] for r in chain_ca_residues(hla_chain)]
    contig = build_contig_template(
        result.peptide_chain_id,
        pep_resseqs,
        result.hla_chain_ids[0],
        hla_resseqs,
        binder_length_min=config.binder_length_min,
        binder_length_max=config.binder_length_max,
    )

    written: list[Path] = []
    for group in config.control_groups:
        hotspots = select_control_hotspots(
            group,
            result.residue_scores,
            allele=example.allele,
            seed=config.seed,
            hotspot_count=n_hotspots,
        )
        if not hotspots:
            logger.warning("No hotspots for %s / %s", example.example_id, group.value)
            continue
        group_patches = (
            result.patches
            if group == ControlGroup.predicted
            else _patches_from_hotspots(hotspots)
        )
        conditioning = build_conditioning(
            example,
            result.residue_scores,
            group_patches,
            hotspots,
            control_group=group,
            config=config,
            contig_template=contig,
        )
        out_path = conditioning_output_path(config.output_dir, example.example_id, group)
        write_conditioning(conditioning, out_path)
        written.append(out_path)

    return written


def export_design_inputs(
    config: DesignExportConfig,
    examples: Optional[Iterable[ComplexExample]] = None,
    *,
    repo_root: Path | None = None,
) -> DesignExportReport:
    """Export design-conditioning YAML for all targets."""
    repo_root = repo_root or Path.cwd()
    report = DesignExportReport()
    items = (
        list(examples)
        if examples is not None
        else load_examples(config.examples_glob, repo_root=repo_root)
    )

    for example in items:
        try:
            paths = export_target(example, config, repo_root=repo_root)
            report.exported.extend(str(p) for p in paths)
        except Exception as exc:
            logger.warning("Skipping %s: %s", example.example_id, exc)
            report.skipped.append({"example_id": example.example_id, "error": str(exc)})

    report_path = config.output_dir / "export_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report.to_dict(), indent=2))
    return report
