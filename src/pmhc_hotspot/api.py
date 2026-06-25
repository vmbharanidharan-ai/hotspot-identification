"""Main public API for pmhc-hotspot."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pmhc_hotspot.constants import DEFAULT_HOTSPOT_CONFIG, DEFAULT_WEIGHTS, RESIDUE_CHEMICAL_SCORE
from pmhc_hotspot.export import build_contig_template
from pmhc_hotspot.features.allele_rules import get_anchor_positions, normalize_allele
from pmhc_hotspot.features.confidence import ConfidenceScorer
from pmhc_hotspot.features.contacts import ContactAnalyzer
from pmhc_hotspot.features.geometry import GeometryCalculator
from pmhc_hotspot.features.mutation import MutationScorer
from pmhc_hotspot.features.positioning import PeptideResidueMap
from pmhc_hotspot.features.sasa import SASACalculator
from pmhc_hotspot.features.surface import residue_surface_from_sasa
from pmhc_hotspot.io import (
    StructureLoader,
    chain_ca_residues,
    get_chain,
    infer_peptide_hla_chains,
    residue_aa1,
)
from pmhc_hotspot.ml.persistence import StagedModelBundle, load_staged_bundle
from pmhc_hotspot.scoring.baseline import HotspotScorer
from pmhc_hotspot.scoring.calibration import minmax_normalize
from pmhc_hotspot.scoring.patches import PatchSelector
from pmhc_hotspot.scoring.selection import select_rfdiffusion_hotspots
from pmhc_hotspot.types import PredictionResult, ResidueScore
from pmhc_hotspot.validation import StructureValidator


class HotspotPredictor:
    """
    Structure-aware hotspot selection for peptide–MHC complexes.

    This is a heuristic, structure-informed prioritization system for
    RFdiffusion binder design — not a predictor of T-cell activation
    or immunogenicity.
    """

    def __init__(
        self,
        allele: str | None = None,
        mutation_positions: list[int] | None = None,
        weights: dict[str, float] | None = None,
        peptide_chain: str | None = None,
        hla_chain: str | None = None,
        hotspot_config: dict | None = None,
        ml_bundle: StagedModelBundle | str | Path | None = None,
        scoring_mode: str = "deterministic",
    ):
        self.allele = normalize_allele(allele)
        self.mutation_positions = mutation_positions or []
        self.weights = weights
        self.peptide_chain = peptide_chain
        self.hla_chain = hla_chain
        self.hotspot_config = {**DEFAULT_HOTSPOT_CONFIG, **(hotspot_config or {})}
        self.scoring_mode = scoring_mode
        if isinstance(ml_bundle, (str, Path)):
            self.ml_bundle = load_staged_bundle(ml_bundle)
        else:
            self.ml_bundle = ml_bundle

        self._loader = StructureLoader()
        self._validator = StructureValidator()
        self._sasa = SASACalculator()
        self._geometry = GeometryCalculator()
        self._contacts = ContactAnalyzer()
        self._mutation = MutationScorer(self.mutation_positions)
        self._confidence = ConfidenceScorer()

    @lru_cache(maxsize=8)
    def _load_cached(self, path: str):
        return self._loader.load(path)

    def predict(self, structure_path: str | Path, *, select_hotspots: bool = True) -> PredictionResult:
        path = str(structure_path)
        structure = self._load_cached(path)

        report = self._validator.validate(structure, self.peptide_chain, self.hla_chain)
        report.raise_if_fatal()

        pep_id, hla_ids = infer_peptide_hla_chains(structure, self.peptide_chain, self.hla_chain)
        pep_chain = get_chain(structure, pep_id)
        hla_chains = [get_chain(structure, hid) for hid in hla_ids]
        hla_residues = [r for chain in hla_chains for r in chain_ca_residues(chain)]

        prm = PeptideResidueMap(pep_chain)
        preferred_positions = prm.preferred_tcr_positions()
        anchor_positions = get_anchor_positions(self.allele, prm.length)
        sasa_result = self._sasa.compute(structure)

        raw_rows: list[dict] = []
        for i, residue in enumerate(prm.residues):
            aa = residue_aa1(residue)
            abs_sasa = self._sasa.residue_sasa(residue, sasa_result)
            rel_sasa = self._sasa.residue_relative_sasa(residue, sasa_result)
            surface = residue_surface_from_sasa(residue, sasa_result, aa=aa)
            hla_contact_count = self._contacts.hla_contacts(residue, hla_residues)
            pep_contact_count = self._contacts.peptide_neighbors(residue, prm.residues, i)
            buried = self._contacts.is_buried(residue, hla_residues, rel_sasa)
            position_1based = i + 1

            raw_rows.append(
                {
                    "residue": residue,
                    "aa": aa,
                    "position_index": i,
                    "position": prm.position_label(i),
                    "normalized_position": prm.normalized_position(i),
                    "abs_sasa": abs_sasa,
                    "rel_sasa": rel_sasa,
                    "hydrophobic_sasa": surface.hydrophobic_sasa,
                    "polar_sasa": surface.polar_sasa,
                    "hydrophobic_fraction": surface.hydrophobic_fraction,
                    "polar_fraction": surface.polar_fraction,
                    "protrusion": self._geometry.protrusion(i, prm.residues),
                    "curvature": self._geometry.curvature(i, prm.residues),
                    "bulge": self._geometry.bulge(i, prm.residues),
                    "hla_contacts": hla_contact_count,
                    "peptide_contacts": pep_contact_count,
                    "mutation_proximity": self._mutation.proximity(i),
                    "confidence": self._confidence.residue_confidence(residue),
                    "tcr_exposure_prior": self._geometry.tcr_exposure_prior(
                        i, prm.residues, preferred_positions
                    ),
                    "chemical_score": RESIDUE_CHEMICAL_SCORE.get(aa, 0.0),
                    "is_anchor": position_1based in anchor_positions,
                    "is_buried": buried,
                }
            )

        max_hla = max((r["hla_contacts"] for r in raw_rows), default=1)
        norm_sasa = minmax_normalize([r["rel_sasa"] for r in raw_rows])
        norm_protrusion = minmax_normalize([r["protrusion"] for r in raw_rows])
        norm_curvature = minmax_normalize([r["curvature"] for r in raw_rows])
        norm_bulge = minmax_normalize([r["bulge"] for r in raw_rows])
        norm_chemical = minmax_normalize([r["chemical_score"] for r in raw_rows])
        norm_tcr = minmax_normalize([r["tcr_exposure_prior"] for r in raw_rows])

        scorer = HotspotScorer(self.allele, self.weights or DEFAULT_WEIGHTS)
        residue_scores: list[ResidueScore] = []

        for j, row in enumerate(raw_rows):
            residue = row["residue"]
            features = {
                "sasa": norm_sasa[j],
                "protrusion": norm_protrusion[j],
                "curvature": norm_curvature[j],
                "bulge": norm_bulge[j],
                "mutation_proximity": row["mutation_proximity"],
                "hla_contact_norm": self._contacts.normalized_hla_contact_burden(
                    row["hla_contacts"], max_hla
                ),
                "tcr_exposure_prior": norm_tcr[j],
                "chemical_norm": norm_chemical[j],
                "confidence": row["confidence"],
            }

            position_1based = row["position_index"] + 1
            score, explanation = scorer.score_residue(
                features,
                position_1based,
                prm.length,
                buried=row["is_buried"],
            )
            anchor_penalty = scorer.anchor_filter.penalty(
                position_1based,
                prm.length,
                buried=row["is_buried"],
                relative_sasa=features["sasa"],
            )

            eligible = row["aa"] not in {"G", "P"}
            low_conf = ConfidenceScorer.is_low_confidence(row["confidence"])

            residue_scores.append(
                ResidueScore(
                    chain_id=pep_id,
                    resseq=residue.id[1],
                    icode=residue.id[2].strip() if len(residue.id) > 2 else "",
                    aa=row["aa"],
                    position=row["position"],
                    position_index=row["position_index"],
                    normalized_position=row["normalized_position"],
                    score=score,
                    sasa=row["abs_sasa"],
                    relative_sasa=row["rel_sasa"],
                    hydrophobic_sasa=row["hydrophobic_sasa"],
                    polar_sasa=row["polar_sasa"],
                    hydrophobic_fraction=row["hydrophobic_fraction"],
                    polar_fraction=row["polar_fraction"],
                    protrusion=row["protrusion"],
                    curvature=row["curvature"],
                    bulge=row["bulge"],
                    hla_contacts=row["hla_contacts"],
                    peptide_contacts=row["peptide_contacts"],
                    mutation_proximity=row["mutation_proximity"],
                    confidence=row["confidence"],
                    anchor_penalty=anchor_penalty,
                    chemical_score=row["chemical_score"],
                    tcr_exposure_prior=row["tcr_exposure_prior"],
                    is_anchor=row["is_anchor"],
                    is_buried=row["is_buried"],
                    low_confidence=low_conf,
                    eligible_for_hotspot=eligible,
                    explanation=explanation,
                )
            )

        if self.scoring_mode != "deterministic" and self.ml_bundle is not None:
            from pmhc_hotspot.ml.inference import (
                blend_residue_scores,
                predict_residue_probabilities,
                predict_statistical_probabilities,
            )

            temp_result = PredictionResult(
                allele=self.allele,
                peptide_chain_id=pep_id,
                hla_chain_ids=hla_ids,
                peptide_sequence=prm.sequence,
                peptide_length=prm.length,
                residue_scores=residue_scores,
                hotspots=[],
                patches=[],
                rfdiffusion_hotspot_res="",
                contig_template="",
                metadata={},
            )
            stat_probs = None
            if self.scoring_mode in {"statistical", "hybrid"} and self.ml_bundle.statistical_model:
                stat_probs = predict_statistical_probabilities(temp_result, self.ml_bundle)
            ml_probs = None
            if self.scoring_mode in {"ml", "hybrid"}:
                ml_probs = predict_residue_probabilities(temp_result, self.ml_bundle)
            ranked = blend_residue_scores(
                residue_scores,
                ml_probs,
                scoring_mode=self.scoring_mode,
                stat_probs=stat_probs,
                hybrid_alpha=self.ml_bundle.hybrid_alpha,
            )
            ranked.sort(key=lambda item: (-item[1], item[0].position_index))
            residue_scores_sorted = [r for r, _ in ranked]
        else:
            residue_scores_sorted = sorted(residue_scores, key=lambda r: r.score, reverse=True)

        patch_selector = PatchSelector(
            min_patch_size=self.hotspot_config["min_patch_size"],
            max_patches=self.hotspot_config["max_patches"],
        )
        patches = patch_selector.select(residue_scores)

        if select_hotspots:
            hotspots = select_rfdiffusion_hotspots(
                residue_scores,
                allele=self.allele,
                min_hotspots=self.hotspot_config["min_hotspots"],
                max_hotspots=self.hotspot_config["max_hotspots"],
                min_hydrophobic=self.hotspot_config["min_hydrophobic"],
            )
            rfdiffusion_hotspot_res = ",".join(h.rfdiffusion_token for h in hotspots)
        else:
            hotspots = []
            rfdiffusion_hotspot_res = ""

        pep_resseqs = [r.id[1] for r in prm.residues]
        hla_resseqs = [r.id[1] for r in chain_ca_residues(hla_chains[0])]
        contig = build_contig_template(pep_id, pep_resseqs, hla_ids[0], hla_resseqs)

        return PredictionResult(
            allele=self.allele,
            peptide_chain_id=pep_id,
            hla_chain_ids=hla_ids,
            peptide_sequence=prm.sequence,
            peptide_length=prm.length,
            residue_scores=residue_scores_sorted,
            hotspots=hotspots,
            patches=patches,
            rfdiffusion_hotspot_res=rfdiffusion_hotspot_res,
            contig_template=contig,
            metadata={
                "warnings": report.warnings,
                "structure_path": path,
                "anchor_positions": sorted(anchor_positions),
                "preferred_tcr_positions": preferred_positions,
                "scoring_mode": self.scoring_mode,
                "ml_bundle_loaded": self.ml_bundle is not None,
                "method": f"pmhc-hotspot {self.scoring_mode} v0.3.0",
                "disclaimer": (
                    "Heuristic design prioritization; not T-cell activation prediction"
                ),
            },
        )

    def _load_structure_for_benchmark(self, pdb_path: str):
        """Load structure without predictor result cache (benchmark labels)."""
        return self._loader.load(pdb_path)

    def benchmark(
        self,
        manifest_path: str | None = None,
        *,
        top_k: tuple[int, ...] = (1, 3, 5),
        download: bool = False,
        cache_dir: str = "data/pdb",
        contact_mode: str = "standard",
        scoring_mode: str | None = None,
        ml_bundle: StagedModelBundle | str | Path | None = None,
    ) -> dict:
        """Run benchmark over curated TCR-bound pMHC structures."""
        from pmhc_hotspot.benchmark.runner import BenchmarkRunner

        mode = scoring_mode or self.scoring_mode
        bundle = ml_bundle if ml_bundle is not None else self.ml_bundle
        return BenchmarkRunner(self).run_manifest(
            manifest_path,
            top_k=top_k,
            download=download,
            cache_dir=cache_dir,
            contact_mode=contact_mode,
            scoring_mode=mode,
            ml_bundle=bundle,
        )

    def build_ml_training_frame(
        self,
        manifest_path: str | None = None,
        *,
        download: bool = True,
        contact_mode: str = "standard",
        cache_dir: str = "data/pdb",
    ):
        """Build residue-level ML training data from benchmark structures."""
        from pmhc_hotspot.ml.dataset import build_training_dataset

        return build_training_dataset(
            manifest_path,
            download=download,
            contact_mode=contact_mode,
            cache_dir=cache_dir,
        )
