"""Gatekeeper verdict from DesignEvalReport (M6)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from pmhc_hotspot.eval.config import EvalConfig
from pmhc_hotspot.schema.design_eval import DesignEvalReport


@dataclass
class GatekeeperDecision:
    verdict: str
    target_id: str
    beats: list[str]
    notes: str = ""

    def to_markdown(self) -> str:
        beats = ", ".join(self.beats) if self.beats else "none"
        return (
            f"{self.verdict}\n\n"
            f"Target: {self.target_id}\n"
            f"Predicted beats: {beats}\n"
            f"{self.notes}\n"
        )


def decide_from_report(report: DesignEvalReport, config: EvalConfig) -> GatekeeperDecision:
    beats = [g.value for g in report.predicted_beats_controls]
    if beats:
        verdict = "APPROVE_PROMOTE"
        notes = f"Primary metric {report.primary_metric}: predicted beats {beats}."
    elif not report.comparisons:
        verdict = "RETRY"
        notes = "Missing control comparisons — run design-export and design-eval."
    else:
        verdict = "REJECT"
        notes = "Predicted did not beat any control within configured tolerance."

    return GatekeeperDecision(
        verdict=verdict,
        target_id=report.target_id,
        beats=beats,
        notes=notes,
    )


def load_ranking_report(path: Path) -> DesignEvalReport:
    return DesignEvalReport.model_validate(json.loads(path.read_text()))


def run_gatekeeper(
    config: EvalConfig,
    target_ids: Optional[Iterable[str]] = None,
    *,
    repo_root: Path | None = None,
) -> list[GatekeeperDecision]:
    root = repo_root or Path.cwd()
    metrics_dir = config.metrics_dir if config.metrics_dir.is_absolute() else root / config.metrics_dir
    reports_dir = root / "artifacts" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    if target_ids is None:
        target_ids = sorted(
            p.parent.name
            for p in metrics_dir.glob("*/ranking_report.json")
            if p.parent.name != "metrics"
        )

    decisions: list[GatekeeperDecision] = []
    for target_id in target_ids:
        report_path = metrics_dir / target_id / "ranking_report.json"
        if not report_path.exists():
            continue
        report = load_ranking_report(report_path)
        decision = decide_from_report(report, config)
        report.gatekeeper_verdict = decision.verdict
        report_path.write_text(json.dumps(report.model_dump(mode="json"), indent=2))
        (reports_dir / f"gatekeeper_{target_id}.md").write_text(decision.to_markdown())
        decisions.append(decision)

    if decisions:
        summary = reports_dir / "gatekeeper_decision.md"
        summary.write_text("\n---\n".join(d.to_markdown() for d in decisions))

    return decisions
