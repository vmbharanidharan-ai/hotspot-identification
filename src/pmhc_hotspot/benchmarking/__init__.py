"""Benchmarking utilities (backward-compatible imports)."""

from pmhc_hotspot.benchmark.metrics import HotspotEvaluator
from pmhc_hotspot.constants import BENCHMARK_PDB_IDS

__all__ = ["BENCHMARK_PDB_IDS", "HotspotEvaluator"]


def __getattr__(name: str):
    """Lazy imports to avoid circular dependencies."""
    if name in {
        "BenchmarkEntry",
        "BenchmarkManifest",
        "BenchmarkRunner",
        "StructureEvaluation",
        "PDBDataset",
        "PDBDownloader",
        "aggregate_results",
        "evaluate_structure",
        "extract_peptide_contact_positions",
    }:
        from pmhc_hotspot import benchmark as _benchmark

        return getattr(_benchmark, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
