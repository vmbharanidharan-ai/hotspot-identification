"""Design validation ranking and stub metrics (M6)."""

from __future__ import annotations

import csv
import json
import logging
import random
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from pmhc_hotspot.eval.config import EvalConfig
from pmhc_hotspot.schema.conditioning import ControlGroup, DesignConditioning
from pmhc_hotspot.schema.design_eval import (
    ControlComparison,
    DesignCandidateMetrics,
    DesignEvalReport,
)

logger = logging.getLogger(__name__)

_GROUP_OFFSETS = {
    ControlGroup.random: 5.0,
    ControlGroup.exposed_only: 3.0,
    ControlGroup.central_only: 2.0,
    ControlGroup.predicted: 0.0,
}


@dataclass
class EvalRunReport:
    targets: list[str] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"targets": self.targets, "skipped": self.skipped}


def _load_conditioning(path: Path) -> DesignConditioning:
    with path.open() as fh:
        data = yaml.safe_load(fh) or {}
    return DesignConditioning.model_validate(data)


def discover_targets(inputs_dir: Path) -> list[str]:
    if not inputs_dir.exists():
        return []
    return sorted(d.name for d in inputs_dir.iterdir() if d.is_dir())


def stub_primary_metric(
    conditioning: DesignConditioning,
    *,
    seed: int,
    primary_metric: str,
) -> float:
    """Proxy metric from conditioning when AF2/MPNN outputs are not wired."""
    rng = random.Random(seed + hash(conditioning.control_group.value))
    n = max(len(conditioning.hotspots), 1)
    mean_conf = sum(h.confidence for h in conditioning.hotspots) / n
    offset = _GROUP_OFFSETS.get(conditioning.control_group, 0.0)
    noise = rng.uniform(-0.3, 0.3)
    if primary_metric == "af2_ipae":
        return 12.0 + offset - 4.0 * mean_conf + noise
    if primary_metric == "hotspot_contact_fraction":
        return 0.35 + mean_conf * 0.4 - offset * 0.02 + noise * 0.01
    return 10.0 + offset - mean_conf + noise


def _read_output_candidates(
    path: Path,
    control_group: ControlGroup,
    target_id: str,
    primary_metric: str,
) -> list[DesignCandidateMetrics]:
    if not path.exists():
        return []
    rows: list[DesignCandidateMetrics] = []
    with path.open() as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            value = row.get(primary_metric)
            metric_value = float(value) if value not in (None, "") else None
            rows.append(
                DesignCandidateMetrics(
                    candidate_id=row.get("candidate_id", ""),
                    control_group=control_group,
                    target_id=target_id,
                    seed=int(row.get("seed", 0)),
                    af2_ipae=metric_value if primary_metric == "af2_ipae" else None,
                    hotspot_contact_fraction=(
                        metric_value if primary_metric == "hotspot_contact_fraction" else None
                    ),
                )
            )
    return rows


def build_target_report(
    target_id: str,
    config: EvalConfig,
    *,
    repo_root: Path | None = None,
) -> DesignEvalReport:
    root = repo_root or Path.cwd()
    inputs_dir = config.inputs_dir if config.inputs_dir.is_absolute() else root / config.inputs_dir
    outputs_dir = config.outputs_dir if config.outputs_dir.is_absolute() else root / config.outputs_dir
    target_inputs = inputs_dir / target_id

    candidates: list[DesignCandidateMetrics] = []
    group_values: Dict[ControlGroup, list[float]] = {g: [] for g in config.control_groups}

    for group in config.control_groups:
        conditioning_path = target_inputs / f"{group.value}.yaml"
        if not conditioning_path.exists():
            raise FileNotFoundError(conditioning_path)

        output_csv = outputs_dir / target_id / group.value / "candidates.csv"
        loaded = _read_output_candidates(output_csv, group, target_id, config.primary_metric)

        if loaded:
            candidates.extend(loaded)
            for row in loaded:
                value = getattr(row, config.primary_metric, None)
                if value is not None:
                    group_values[group].append(float(value))
        elif config.stub_mode:
            conditioning = _load_conditioning(conditioning_path)
            value = stub_primary_metric(
                conditioning,
                seed=config.seed,
                primary_metric=config.primary_metric,
            )
            group_values[group].append(value)
            candidates.append(
                DesignCandidateMetrics(
                    candidate_id=f"{target_id}_{group.value}_stub",
                    control_group=group,
                    target_id=target_id,
                    seed=config.seed,
                    **{config.primary_metric: value},
                )
            )
        else:
            raise FileNotFoundError(
                f"Missing design outputs for {target_id}/{group.value} and stub_mode is off"
            )

    comparisons: list[ControlComparison] = []
    for group, values in group_values.items():
        if not values:
            continue
        comparisons.append(
            ControlComparison(
                control_group=group,
                n_candidates=len(values),
                primary_metric=config.primary_metric,
                mean_primary=statistics.mean(values),
                median_primary=statistics.median(values),
                best_primary=min(values) if not config.higher_is_better else max(values),
            )
        )

    predicted_beats = _predicted_beats_controls(comparisons, config)

    return DesignEvalReport(
        target_id=target_id,
        primary_metric=config.primary_metric,
        higher_is_better=config.higher_is_better,
        comparisons=comparisons,
        candidates=candidates,
        predicted_beats_controls=predicted_beats,
        notes="stub_mode" if config.stub_mode else "live_outputs",
    )


def _predicted_beats_controls(
    comparisons: list[ControlComparison],
    config: EvalConfig,
) -> list[ControlGroup]:
    predicted = next(
        (c for c in comparisons if c.control_group == ControlGroup.predicted),
        None,
    )
    if predicted is None or predicted.mean_primary is None:
        return []

    beats: list[ControlGroup] = []
    for comp in comparisons:
        if comp.control_group == ControlGroup.predicted:
            continue
        if comp.mean_primary is None:
            continue
        if config.higher_is_better:
            threshold = comp.mean_primary * (1.0 + config.min_improvement_fraction)
            if predicted.mean_primary > threshold:
                beats.append(comp.control_group)
        else:
            if predicted.mean_primary < comp.mean_primary - config.tolerance:
                beats.append(comp.control_group)
    return beats


def write_ranking_report(report: DesignEvalReport, metrics_dir: Path) -> Path:
    out_dir = metrics_dir / report.target_id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "ranking_report.json"
    path.write_text(json.dumps(report.model_dump(mode="json"), indent=2))
    return path


def run_design_eval(
    config: EvalConfig,
    *,
    repo_root: Path | None = None,
) -> EvalRunReport:
    root = repo_root or Path.cwd()
    metrics_dir = config.metrics_dir if config.metrics_dir.is_absolute() else root / config.metrics_dir
    inputs_dir = config.inputs_dir if config.inputs_dir.is_absolute() else root / config.inputs_dir
    run_report = EvalRunReport()

    for target_id in discover_targets(inputs_dir):
        try:
            report = build_target_report(target_id, config, repo_root=root)
            write_ranking_report(report, metrics_dir)
            run_report.targets.append(target_id)
        except Exception as exc:
            logger.warning("Eval skip %s: %s", target_id, exc)
            run_report.skipped.append({"target_id": target_id, "error": str(exc)})

    summary_path = metrics_dir / "eval_run_report.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(run_report.to_dict(), indent=2))
    return run_report
