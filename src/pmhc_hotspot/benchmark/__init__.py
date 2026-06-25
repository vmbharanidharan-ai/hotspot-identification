"""Benchmarking over curated TCR-bound pMHC structures."""

from pmhc_hotspot.benchmark.evaluate import StructureEvaluation, aggregate_results, evaluate_structure
from pmhc_hotspot.benchmark.manifest import BenchmarkEntry, BenchmarkManifest
from pmhc_hotspot.benchmark.metrics import HotspotEvaluator
from pmhc_hotspot.benchmark.runner import BenchmarkRunner

__all__ = [
    "BenchmarkEntry",
    "BenchmarkManifest",
    "BenchmarkRunner",
    "HotspotEvaluator",
    "StructureEvaluation",
    "aggregate_results",
    "evaluate_structure",
]
