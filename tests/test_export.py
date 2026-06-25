"""Tests for export."""

import json
from pathlib import Path

from pmhc_hotspot import HotspotPredictor
from pmhc_hotspot.export import export_rfdiffusion_template, to_json, to_tsv


def test_export_roundtrip(fixture_pdb, tmp_path):
    result = HotspotPredictor(allele="HLA-A*02:01").predict(fixture_pdb)
    tsv_path = tmp_path / "out.tsv"
    json_path = tmp_path / "out.json"
    yaml_path = tmp_path / "out.yaml"

    to_tsv(result, tsv_path)
    to_json(result, json_path)
    export_rfdiffusion_template(result, yaml_path)

    assert tsv_path.exists()
    data = json.loads(json_path.read_text())
    assert data["peptide_length"] == 9
    assert "rfdiffusion_hotspot_res" in data
    assert yaml_path.exists()
