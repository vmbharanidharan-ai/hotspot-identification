"""Benchmark evaluation tests."""

from pmhc_hotspot.benchmark.evaluate import aggregate_results, evaluate_structure
from pmhc_hotspot.benchmark.manifest import BenchmarkManifest


def test_default_manifest_has_15_structures():
    manifest = BenchmarkManifest.default()
    assert len(manifest) >= 15


def test_evaluate_structure_metrics():
    ev = evaluate_structure(
        pdb_id="TEST",
        predicted_ordered=["P4", "P5", "P6", "P7", "P8"],
        truth_positions={"P5", "P6", "P7"},
        allele="HLA-A*02:01",
        peptide_length=9,
        top_k=(3, 5),
    )
    assert ev.recall_at_k[3] > 0
    assert ev.recall_at_k[5] >= ev.recall_at_k[3]
    assert 0.0 <= ev.anchor_avoidance_at_k[5] <= 1.0


def test_runner_local_mini_manifest():
    from pmhc_hotspot import HotspotPredictor

    report = HotspotPredictor(allele="HLA-A*02:01").benchmark(
        "tests/data/benchmark_mini.yaml",
        download=False,
    )
    assert "summary" in report
    assert len(report["results"]) == 1


def test_aggregate_results_by_length():
    from pmhc_hotspot.benchmark.evaluate import StructureEvaluation

    rows = [
        StructureEvaluation("A", "HLA-A*02:01", 9, 3, recall_at_k={5: 0.6}),
        StructureEvaluation("B", "HLA-A*02:01", 10, 2, recall_at_k={5: 0.4}),
    ]
    summary = aggregate_results(rows)
    assert summary["n_structures"] == 2
    assert "8-9" in summary["by_peptide_length"]
