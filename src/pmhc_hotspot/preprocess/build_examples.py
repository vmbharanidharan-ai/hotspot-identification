"""Build canonical ComplexExample JSON from structures (Phase 1 ingest)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pmhc_hotspot.benchmark.contact_labels import ContactMode
from pmhc_hotspot.benchmark.dataset import (
    PDBDownloader,
    extract_peptide_contact_positions,
    resolve_benchmark_entry,
)
from pmhc_hotspot.benchmark.manifest import BenchmarkEntry, BenchmarkManifest
from pmhc_hotspot.benchmark.stcrdab import convert_stcrdab_summary, default_eval_pdb_ids
from pmhc_hotspot.features.positioning import PeptideResidueMap
from pmhc_hotspot.io import StructureLoader, get_chain
from pmhc_hotspot.preprocess.config import DatasetBuildConfig
from pmhc_hotspot.schema.examples import (
    ComplexExample,
    ExampleLabels,
    ExampleProvenance,
    ExampleSplit,
)

logger = logging.getLogger(__name__)


@dataclass
class IngestReport:
    built: list[str] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    holdout_ids: list[str] = field(default_factory=list)
    train_ids: list[str] = field(default_factory=list)
    stcrdab_report: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _entry_from_row(row: dict[str, Any]) -> BenchmarkEntry:
    tcr = row.get("tcr_chains") or []
    return BenchmarkEntry(
        pdb_id=str(row["pdb_id"]).upper(),
        allele=row.get("allele"),
        peptide_chain=row.get("peptide_chain"),
        hla_chain=row.get("hla_chain"),
        tcr_chains=tuple(str(c) for c in tcr),
        pdb_path=row.get("pdb_path"),
        notes=row.get("notes", ""),
    )


def _example_id(entry: BenchmarkEntry) -> str:
    allele = (entry.allele or "unknown").replace("*", "").replace(":", "")
    return f"{entry.pdb_id}_{allele}"


def _split_for_pdb(pdb_id: str, holdout_ids: set[str]) -> ExampleSplit:
    if pdb_id.upper() in holdout_ids:
        return ExampleSplit.holdout
    return ExampleSplit.train


def build_example_from_entry(
    entry: BenchmarkEntry,
    *,
    structure_path: Path,
    split: ExampleSplit,
    contact_mode: ContactMode = "standard",
    source: str = "pdb",
    manifest_path: str | None = None,
) -> ComplexExample:
    loader = StructureLoader()
    structure = loader.load(structure_path)
    resolved = resolve_benchmark_entry(structure, entry)

    pep_chain = get_chain(structure, resolved.peptide_chain)
    prm = PeptideResidueMap(pep_chain)
    contacted = extract_peptide_contact_positions(
        structure, resolved, contact_mode=contact_mode
    )

    hla_chains = [resolved.hla_chain] if resolved.hla_chain else []
    return ComplexExample(
        example_id=_example_id(resolved),
        allele=resolved.allele,
        peptide_chain=resolved.peptide_chain or pep_chain.id,
        hla_chains=[c for c in hla_chains if c],
        tcr_chains=list(resolved.tcr_chains),
        peptide_sequence=prm.sequence,
        peptide_length=prm.length,
        structure_path=str(structure_path.resolve()),
        split=split,
        provenance=ExampleProvenance(
            pdb_id=resolved.pdb_id,
            source=source,
            structure_path=str(structure_path.resolve()),
            manifest_path=manifest_path,
            downloaded_at=datetime.now(timezone.utc).isoformat(),
        ),
        labels=ExampleLabels(
            contact_mode=contact_mode,
            tcr_contact_positions=sorted(contacted),
        ),
    )


def _collect_entries(config: DatasetBuildConfig) -> tuple[list[BenchmarkEntry], IngestReport]:
    report = IngestReport()
    holdout_ids = default_eval_pdb_ids()
    report.holdout_ids = sorted(holdout_ids)
    entries: list[BenchmarkEntry] = []
    seen: set[str] = set()

    if "pdb_manifest" in config.sources:
        manifest = BenchmarkManifest.resolve(config.holdout_manifest)
        for entry in manifest:
            entries.append(entry)
            seen.add(entry.pdb_id.upper())

    for extra in config.extra_manifests:
        manifest = BenchmarkManifest.resolve(extra)
        for entry in manifest:
            if entry.pdb_id.upper() not in seen:
                entries.append(entry)
                seen.add(entry.pdb_id.upper())

    if "stcrdab" in config.sources:
        if config.stcrdab_path is None or not config.stcrdab_path.exists():
            report.skipped.append(
                {"reason": "stcrdab_path_missing", "path": str(config.stcrdab_path)}
            )
        else:
            rows, st_report = convert_stcrdab_summary(
                config.stcrdab_path,
                exclude_pdb_ids=holdout_ids if config.stcrdab_exclude_eval else set(),
                max_resolution=config.stcrdab_max_resolution,
            )
            report.stcrdab_report = st_report
            for row in rows:
                pdb_id = row["pdb_id"].upper()
                if pdb_id in seen:
                    continue
                entries.append(_entry_from_row(row))
                seen.add(pdb_id)

    return entries, report


def write_example(example: ComplexExample, output_dir: Path) -> Path:
    split_dir = output_dir / "examples" / example.split.value
    split_dir.mkdir(parents=True, exist_ok=True)
    path = split_dir / f"{example.example_id}.json"
    path.write_text(json.dumps(example.model_dump(mode="json"), indent=2))
    return path


def build_dataset(
    config: DatasetBuildConfig,
    *,
    repo_root: Path | None = None,
) -> IngestReport:
    """Download structures and emit ComplexExample JSON files."""
    repo_root = repo_root or Path.cwd()
    holdout_ids = default_eval_pdb_ids()
    entries, report = _collect_entries(config)
    downloader = PDBDownloader(config.cache_dir)
    contact_mode: ContactMode = config.contact_mode  # type: ignore[assignment]

    config.processed_dir.mkdir(parents=True, exist_ok=True)

    for entry in entries:
        pdb_id = entry.pdb_id.upper()
        split = _split_for_pdb(pdb_id, holdout_ids)
        try:
            if entry.pdb_path and Path(entry.pdb_path).exists():
                structure_path = Path(entry.pdb_path)
            elif config.download:
                structure_path = downloader.download(pdb_id)
            else:
                structure_path = downloader.pdb_path(pdb_id)
                if not structure_path.exists():
                    raise FileNotFoundError(structure_path)

            example = build_example_from_entry(
                entry,
                structure_path=structure_path,
                split=split,
                contact_mode=contact_mode,
                source="stcrdab" if pdb_id not in holdout_ids else "pdb_holdout",
                manifest_path=str(config.holdout_manifest),
            )
            write_example(example, config.processed_dir)
            report.built.append(example.example_id)
            if split == ExampleSplit.train:
                report.train_ids.append(example.example_id)
        except Exception as exc:
            msg = str(exc)
            logger.warning("Skipping %s: %s", pdb_id, msg)
            if config.skip_missing:
                report.skipped.append({"pdb_id": pdb_id, "error": msg})
            else:
                raise

    manifest_payload = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "n_built": len(report.built),
        "n_skipped": len(report.skipped),
        "holdout_ids": report.holdout_ids,
        "examples": report.built,
        "skipped": report.skipped,
        "stcrdab": report.stcrdab_report,
    }
    config.output_manifest.parent.mkdir(parents=True, exist_ok=True)
    config.output_manifest.write_text(json.dumps(manifest_payload, indent=2))
    ingest_report_path = config.processed_dir / "ingest_report.json"
    ingest_report_path.write_text(json.dumps(report.to_dict(), indent=2))

    return report
