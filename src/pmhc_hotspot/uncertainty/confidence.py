"""Prediction confidence and calibration (Phase 0.3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

from pmhc_hotspot.types import PredictionResult, ResidueScore


@dataclass
class ResidueConfidence:
    position: str
    position_index: int
    score: float
    calibrated_probability: float
    confidence_level: str
    std_dev: float
    uncertainty_sources: List[str]
    rationale: str


class ConfidenceEstimator:
    """Platt-style calibration, CV disagreement proxy, and feature jitter."""

    def __init__(
        self,
        *,
        jitter_fraction: float = 0.05,
        high_threshold: float = 0.75,
        low_threshold: float = 0.45,
    ):
        self.jitter_fraction = jitter_fraction
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self._platt_a = 1.0
        self._platt_b = 0.0

    def fit_platt(self, scores: np.ndarray, labels: np.ndarray) -> None:
        """Fit Platt scaling on validation scores (logistic on logit)."""
        try:
            from sklearn.linear_model import LogisticRegression
        except ImportError as exc:
            raise ImportError('Install sklearn: pip install -e ".[ml]"') from exc

        scores = np.clip(scores, 1e-6, 1 - 1e-6)
        logits = np.log(scores / (1 - scores)).reshape(-1, 1)
        clf = LogisticRegression(max_iter=1000)
        clf.fit(logits, labels.astype(int))
        self._platt_a = float(clf.coef_[0, 0])
        self._platt_b = float(clf.intercept_[0])

    def calibrate_score(self, score: float) -> float:
        score = float(np.clip(score, 1e-6, 1 - 1e-6))
        logit = np.log(score / (1 - score))
        scaled = self._platt_a * logit + self._platt_b
        return float(1.0 / (1.0 + np.exp(-scaled)))

    def feature_jitter_std(
        self,
        residue: ResidueScore,
        scorer,
        *,
        n_samples: int = 8,
        rng: Optional[np.random.Generator] = None,
    ) -> float:
        """Std dev of score under ±jitter_fraction perturbation of normalized features."""
        rng = rng or np.random.default_rng(0)
        base_features = {
            "sasa": residue.relative_sasa,
            "protrusion": residue.protrusion,
            "curvature": residue.curvature,
            "bulge": residue.bulge,
            "mutation_proximity": residue.mutation_proximity,
            "hla_contact_norm": min(1.0, residue.hla_contacts / 10.0),
            "tcr_exposure_prior": residue.tcr_exposure_prior,
            "chemical_norm": residue.chemical_score / 10.0,
            "confidence": residue.confidence,
        }
        scores: list[float] = []
        position_1based = residue.position_index + 1
        for _ in range(n_samples):
            perturbed = {}
            for key, val in base_features.items():
                noise = 1.0 + rng.uniform(-self.jitter_fraction, self.jitter_fraction)
                perturbed[key] = float(np.clip(val * noise, 0.0, 1.0))
            s, _ = scorer.score_residue(
                perturbed,
                position_1based,
                max(position_1based, 9),
                buried=residue.is_buried,
            )
            scores.append(s)
        return float(np.std(scores)) if scores else 0.0

    def level_from_probability(self, prob: float, std_dev: float) -> str:
        if prob >= self.high_threshold and std_dev < 0.08:
            return "high"
        if prob <= self.low_threshold or std_dev > 0.15:
            return "low"
        return "medium"

    def estimate_for_result(
        self,
        result: PredictionResult,
        *,
        scorer=None,
        cv_disagreement: Optional[Dict[str, float]] = None,
    ) -> List[ResidueConfidence]:
        cv_disagreement = cv_disagreement or {}
        outputs: list[ResidueConfidence] = []
        for residue in result.residue_scores:
            calibrated = self.calibrate_score(residue.score)
            jitter_std = 0.0
            sources: list[str] = []
            if scorer is not None:
                jitter_std = self.feature_jitter_std(residue, scorer)
                if jitter_std > 0.05:
                    sources.append("feature_noise")
            cv_std = float(cv_disagreement.get(residue.position, 0.0))
            if cv_std > 0.05:
                sources.append("model_disagreement")
            std_dev = float(np.sqrt(jitter_std**2 + cv_std**2))
            level = self.level_from_probability(calibrated, std_dev)
            outputs.append(
                ResidueConfidence(
                    position=residue.position,
                    position_index=residue.position_index,
                    score=residue.score,
                    calibrated_probability=calibrated,
                    confidence_level=level,
                    std_dev=std_dev,
                    uncertainty_sources=sources or ["heuristic"],
                    rationale=f"calibrated={calibrated:.2f}, std={std_dev:.3f}",
                )
            )
        return outputs


def confidence_to_yaml(
    result: PredictionResult,
    confidences: List[ResidueConfidence],
    output_file: str,
    *,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    import yaml

    payload = {
        "metadata": metadata or {},
        "residue_confidence": [
            {
                "position": c.position,
                "score": c.score,
                "confidence": c.confidence_level,
                "calibrated_probability": c.calibrated_probability,
                "std_dev": c.std_dev,
                "uncertainty_sources": c.uncertainty_sources,
            }
            for c in confidences
        ],
        "hotspots": [
            {
                "position": h.position,
                "score": h.score,
                "rfdiffusion_token": h.rfdiffusion_token,
            }
            for h in result.hotspots
        ],
    }
    with open(output_file, "w") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False)
    return output_file
