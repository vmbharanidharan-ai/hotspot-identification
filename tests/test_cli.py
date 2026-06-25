"""Tests for CLI."""

from click.testing import CliRunner

from pmhc_hotspot.cli import main


def test_cli_run(fixture_pdb, tmp_path):
    runner = CliRunner()
    out = tmp_path / "hotspots.tsv"
    result = runner.invoke(
        main,
        ["run", fixture_pdb, "--allele", "HLA-A*02:01", "--out", str(out)],
    )
    assert result.exit_code == 0
    assert out.exists()


def test_cli_validate(fixture_pdb):
    runner = CliRunner()
    result = runner.invoke(main, ["validate", fixture_pdb])
    assert result.exit_code == 0
