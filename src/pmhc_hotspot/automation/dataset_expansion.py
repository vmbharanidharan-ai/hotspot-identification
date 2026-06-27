"""Dataset expansion orchestration (Phase 1)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import yaml

from pmhc_hotspot.automation.label_generator import ContactLabelGenerator, batch_label_all_pdbs
from pmhc_hotspot.automation.pdb_crawler import PDBCrawler, PDBStructureAnalyzer
from pmhc_hotspot.benchmark.stcrdab import default_eval_pdb_ids


@dataclass
class DatasetExpansionReport:
    total_downloaded: int = 0
    passed_qc: int = 0
    rejected: List[dict] = field(default_factory=list)
    training_set: List[str] = field(default_factory=list)
    new_eval_candidates: List[str] = field(default_factory=list)
    contact_stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def run_dataset_expansion(
    *,
    cache_dir: Path = Path("data/pdb"),
    crawl: bool = True,
    pdb_ids: Optional[List[str]] = None,
    label: bool = True,
    holdout_ids: Optional[set[str]] = None,
) -> DatasetExpansionReport:
    """Crawl, QC, and label structures for dataset expansion."""
    holdout_ids = holdout_ids or {p.upper() for p in default_eval_pdb_ids()}
    crawler = PDBCrawler(cache_dir=cache_dir)
    entries = crawler.crawl(pdb_ids=pdb_ids, download=crawl)
    report = DatasetExpansionReport(total_downloaded=len(entries))

    passed: list[str] = []
    for entry in entries:
        if entry.passed_qc:
            passed.append(entry.pdb_id)
            report.passed_qc += 1
        else:
            report.rejected.append({"pdb_id": entry.pdb_id, "reason": entry.notes})

    crawl_path = crawler.write_results(entries, cache_dir)
    if label and passed:
        label_summary = batch_label_all_pdbs(cache_dir, crawl_path, n_workers=1)
        report.contact_stats = {
            "n_labeled": len(label_summary.get("labeled", [])),
            "contact_entropy_mean": label_summary.get("contact_entropy_mean", 0.0),
        }

    report.training_set = [p for p in passed if p.upper() not in holdout_ids]
    report.new_eval_candidates = [p for p in passed if p.upper() not in holdout_ids][:30]
    return report


def write_clean_structures_report(report: DatasetExpansionReport, output_dir: Path = Path("data/pdb")) -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"clean_structures_{stamp}.json"
    path.write_text(json.dumps(report.to_dict(), indent=2))
    return path


def write_training_set_yaml(
    pdb_ids: List[str],
    output_path: Path = Path("data/pdb/training_set.yaml"),
    *,
    source: str = "crawled",
) -> Path:
    payload = {
        "training_structures": [
            {"pdb_id": pid, "source": source, "qc_flags": []} for pid in sorted(pdb_ids)
        ]
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(payload, sort_keys=False))
    return output_path
