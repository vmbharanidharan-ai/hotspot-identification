"""Benchmark evaluation tests."""

from pmhc_hotspot.benchmark.evaluate import aggregate_results, evaluate_structure
from pmhc_hotspot.benchmark.manifest import BenchmarkManifest


def test_default_manifest_has_structures():
    manifest = BenchmarkManifest.default()
    assert len(manifest) >= 11


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


def test_suggest_benchmark_chains_1bd2():
    from pmhc_hotspot.benchmark.dataset import suggest_benchmark_chains

    suggested = suggest_benchmark_chains({"A": 275, "B": 99, "C": 9, "D": 190, "E": 242})
    assert suggested == {"peptide_chain": "C", "hla_chain": "A", "tcr_chains": ("E", "D")}


def test_resolve_benchmark_entry_falls_back():
    from Bio.PDB import PDBParser

    from pmhc_hotspot.benchmark.dataset import resolve_benchmark_entry
    from pmhc_hotspot.benchmark.manifest import BenchmarkEntry

    structure = PDBParser(QUIET=True).get_structure("x", "data/pdb/5BRZ.pdb")
    entry = BenchmarkEntry(
        pdb_id="5BRZ",
        allele="HLA-A*02:01",
        peptide_chain="P",
        hla_chain="M",
        tcr_chains=("D", "E"),
        pdb_path="data/pdb/5BRZ.pdb",
    )
    resolved = resolve_benchmark_entry(structure, entry)
    assert resolved.peptide_chain == "C"
    assert resolved.hla_chain == "A"


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
