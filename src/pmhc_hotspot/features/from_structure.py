"""Map structure scores to canonical ResidueFeatures on ComplexExample."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pmhc_hotspot.api import HotspotPredictor
from pmhc_hotspot.docking import DockingPriorConfig, compute_docking_priors
from pmhc_hotspot.schema.examples import ComplexExample, ResidueFeatures
from pmhc_hotspot.types import ResidueScore


def residue_score_to_features(
    score: ResidueScore,
    *,
    docking_contact_prior: Optional[float] = None,
) -> ResidueFeatures:
    return ResidueFeatures(
        position=score.position,
        position_index=score.position_index,
        aa=score.aa,
        sasa=score.sasa,
        relative_sasa=score.relative_sasa,
        hydrophobic_fraction=score.hydrophobic_fraction,
        polar_fraction=score.polar_fraction,
        protrusion=score.protrusion,
        curvature=score.curvature,
        bulge=score.bulge,
        hla_contacts=score.hla_contacts,
        peptide_contacts=score.peptide_contacts,
        mutation_proximity=score.mutation_proximity,
        confidence=score.confidence,
        anchor_penalty=score.anchor_penalty,
        chemical_score=score.chemical_score,
        tcr_exposure_prior=score.tcr_exposure_prior,
        buried=score.is_buried,
        is_anchor=score.is_anchor,
        docking_contact_prior=docking_contact_prior,
    )


def compute_example_features(
    example: ComplexExample,
    *,
    scoring_mode: str = "deterministic",
    model_bundle: Path | None = None,
    repo_root: Path | None = None,
    docking_prior: bool = False,
    docking_config: Path | None = None,
) -> list[ResidueFeatures]:
    """Compute per-residue features for one ComplexExample."""
    root = repo_root or Path.cwd()
    structure_path = Path(example.structure_path)
    if not structure_path.is_absolute():
        structure_path = root / structure_path
    if not structure_path.exists():
        raise FileNotFoundError(structure_path)

    predictor = HotspotPredictor(
        allele=example.allele,
        peptide_chain=example.peptide_chain,
        hla_chain=example.hla_chains[0] if example.hla_chains else None,
        scoring_mode=scoring_mode,
        ml_bundle=model_bundle,
    )
    result = predictor.predict(structure_path, select_hotspots=False)
    if len(result.residue_scores) != example.peptide_length:
        raise ValueError(
            f"Feature length mismatch for {example.example_id}: "
            f"{len(result.residue_scores)} vs {example.peptide_length}"
        )

    priors_by_index: dict[int, float] = {}
    if docking_prior:
        dock_cfg_path = docking_config or Path("configs/docking.yaml")
        if not dock_cfg_path.is_absolute():
            dock_cfg_path = root / dock_cfg_path
        dock_cfg = DockingPriorConfig.from_yaml(dock_cfg_path)
        for score, prior in zip(
            result.residue_scores,
            compute_docking_priors(result.residue_scores, dock_cfg),
        ):
            priors_by_index[score.position_index] = prior

    ordered_scores = sorted(result.residue_scores, key=lambda r: r.position_index)
    return [
        residue_score_to_features(
            score,
            docking_contact_prior=priors_by_index.get(score.position_index)
            if docking_prior
            else None,
        )
        for score in ordered_scores
    ]


def enrich_example(
    example: ComplexExample,
    *,
    scoring_mode: str = "deterministic",
    model_bundle: Path | None = None,
    repo_root: Path | None = None,
    docking_prior: bool = False,
    docking_config: Path | None = None,
) -> ComplexExample:
    features = compute_example_features(
        example,
        scoring_mode=scoring_mode,
        model_bundle=model_bundle,
        repo_root=repo_root,
        docking_prior=docking_prior,
        docking_config=docking_config,
    )
    return example.model_copy(update={"residue_features": features})
