#!/usr/bin/env python3
"""Convert an STCRDab summary TSV into a pmhc-hotspot training manifest YAML."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pmhc_hotspot.benchmark.manifest import BenchmarkManifest
from pmhc_hotspot.benchmark.stcrdab import convert_stcrdab_summary, write_training_manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "summary_tsv",
        type=Path,
        help="STCRDab download summary TSV (e.g. 20260626_0032866_summary.tsv)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("data/training_manifest.yaml"),
        help="Output manifest YAML path",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("artifacts/reports/stcrdab_manifest_report.json"),
        help="Write filtering summary JSON here",
    )
    parser.add_argument(
        "--exclude-eval",
        action="store_true",
        default=True,
        help="Exclude bundled benchmark eval PDB IDs (default: true)",
    )
    parser.add_argument(
        "--include-eval",
        action="store_true",
        help="Allow eval manifest PDB IDs in training manifest",
    )
    parser.add_argument(
        "--exclude-pdb",
        action="append",
        default=[],
        help="Additional PDB IDs to exclude (repeatable)",
    )
    parser.add_argument(
        "--max-resolution",
        type=float,
        default=3.5,
        help="Skip structures above this resolution (Å); use 0 to disable",
    )
    parser.add_argument(
        "--engineered",
        choices=["include", "exclude"],
        default="include",
        help="Whether to include engineered TCR structures",
    )
    parser.add_argument(
        "--min-peptide-length",
        type=int,
        default=8,
    )
    parser.add_argument(
        "--max-peptide-length",
        type=int,
        default=15,
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.summary_tsv.exists():
        print(f"Summary TSV not found: {args.summary_tsv}", file=sys.stderr)
        return 1

    exclude: set[str] = {p.upper() for p in args.exclude_pdb}
    if args.exclude_eval and not args.include_eval:
        exclude |= {entry.pdb_id.upper() for entry in BenchmarkManifest.default()}

    max_resolution = None if args.max_resolution <= 0 else args.max_resolution
    structures, report = convert_stcrdab_summary(
        args.summary_tsv,
        exclude_pdb_ids=exclude,
        min_peptide_length=args.min_peptide_length,
        max_peptide_length=args.max_peptide_length,
        max_resolution=max_resolution,
        engineered=args.engineered,
    )
    write_training_manifest(structures, args.output)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w") as fh:
        json.dump(report, fh, indent=2)

    print(f"Wrote {args.output} ({len(structures)} structures)")
    print(f"Wrote {args.report}")
    print(f"Excluded rows/structures: {len(report['excluded'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
