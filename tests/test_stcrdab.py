"""Tests for STCRDab manifest conversion."""

from pathlib import Path

from pmhc_hotspot.benchmark.manifest import BenchmarkManifest
from pmhc_hotspot.benchmark.stcrdab import (
    convert_stcrdab_summary,
    estimate_peptide_length,
    infer_allele,
    write_training_manifest,
)


def test_infer_allele_from_compound():
    assert infer_allele("HLA-B*35:08-13mer peptide") == "HLA-B*35:08"
    assert infer_allele("TCR bound to HLA A2*01-SLLMWITQV") == "HLA-A*02:01"


def test_estimate_peptide_length():
    assert estimate_peptide_length("ebv peptide lpeplpqgqltay") == 13
    assert estimate_peptide_length(None, "HLA-B*35:08-13mer peptide") == 13
    assert estimate_peptide_length("mart-1(27-35) peptide") is None


def test_convert_stcrdab_summary_filters_and_dedupes(tmp_path):
    structures, report = convert_stcrdab_summary(
        "tests/data/stcrdab_mini.tsv",
        exclude_pdb_ids={entry.pdb_id.upper() for entry in BenchmarkManifest.default()},
        max_resolution=3.5,
    )
    pdb_ids = {row["pdb_id"] for row in structures}
    assert "2AK4" in pdb_ids
    assert "3QDJ" in pdb_ids
    assert "5BRZ" not in pdb_ids
    assert "6AVF" not in pdb_ids
    assert report["included"] == 2

    out = tmp_path / "training_manifest.yaml"
    write_training_manifest(structures, out)
    text = out.read_text()
    assert "pdb_id: 2AK4" in text or "pdb_id: '2AK4'" in text
    assert "peptide_chain" in text
