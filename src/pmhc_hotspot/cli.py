"""Command-line interface for pmhc-hotspot."""

from __future__ import annotations

import json

import click

from pmhc_hotspot.api import HotspotPredictor
from pmhc_hotspot.explain import format_explanation
from pmhc_hotspot.export import export_rfdiffusion_template, to_json, to_tsv
from pmhc_hotspot.features.mutation import MutationScorer


@click.group()
@click.version_option(package_name="pmhc-hotspot")
def main():
    """Structure-aware hotspot selection for peptide–MHC binder design."""


@main.command("run")
@click.argument("structure_path", type=click.Path(exists=True))
@click.option("--allele", default=None, help="HLA allele, e.g. HLA-A*02:01 or HLA-A02:01")
@click.option("--mutation", multiple=True, help="Mutation position: P5 or 5 (1-based)")
@click.option("--peptide-chain", default=None, help="Peptide chain ID (auto-detect if omitted)")
@click.option("--hla-chain", default=None, help="HLA chain ID (auto-detect if omitted)")
@click.option("--out", "out_tsv", default="hotspots.tsv", help="Output TSV path")
@click.option("--json-out", default=None, help="Optional JSON output path")
def run_cmd(
    structure_path,
    allele,
    mutation,
    peptide_chain,
    hla_chain,
    out_tsv,
    json_out,
):
    """Score peptide hotspots for a pMHC structure."""
    predictor = HotspotPredictor(
        allele=allele,
        peptide_chain=peptide_chain,
        hla_chain=hla_chain,
    )
    # Parse mutations after loading isn't needed — use placeholder length
    if mutation:
        positions = MutationScorer.parse_mutation_positions(list(mutation), peptide_length=15)
        predictor = HotspotPredictor(
            allele=allele,
            mutation_positions=positions,
            peptide_chain=peptide_chain,
            hla_chain=hla_chain,
        )

    result = predictor.predict(structure_path)
    to_tsv(result, out_tsv)
    click.echo(f"Wrote {out_tsv}")

    if json_out:
        to_json(result, json_out)
        click.echo(f"Wrote {json_out}")

    click.echo(f"Allele: {result.allele or 'unknown (generic MHC-I rules)'}")
    click.echo(f"Peptide ({result.peptide_chain_id}): {result.peptide_sequence}")
    click.echo(f"RFdiffusion hotspots: {result.rfdiffusion_hotspot_res}")
    for w in result.metadata.get("warnings", []):
        click.echo(f"Warning: {w}", err=True)


@main.command("explain")
@click.argument("structure_path", type=click.Path(exists=True))
@click.option("--allele", default=None)
@click.option("--peptide-chain", default=None)
@click.option("--hla-chain", default=None)
def explain_cmd(structure_path, allele, peptide_chain, hla_chain):
    """Show per-residue score breakdown."""
    result = HotspotPredictor(
        allele=allele,
        peptide_chain=peptide_chain,
        hla_chain=hla_chain,
    ).predict(structure_path)

    click.echo(f"{'Pos':<6} {'AA':<4} {'Score':<8} Explanation")
    click.echo("-" * 60)
    for r in sorted(result.residue_scores, key=lambda x: x.position_index):
        click.echo(
            f"{r.position:<6} {r.aa:<4} {r.score:<8.3f} {format_explanation(r)}"
        )


@main.command("export-rfdiffusion")
@click.argument("structure_path", type=click.Path(exists=True))
@click.argument("output_yaml")
@click.option("--allele", default=None)
@click.option("--binder-min", default=50, show_default=True)
@click.option("--binder-max", default=80, show_default=True)
@click.option("--num-designs", default=100, show_default=True)
def export_rfdiffusion_cmd(
    structure_path,
    output_yaml,
    allele,
    binder_min,
    binder_max,
    num_designs,
):
    """Export RFdiffusion config template with selected hotspots."""
    result = HotspotPredictor(allele=allele).predict(structure_path)
    export_rfdiffusion_template(
        result,
        output_yaml,
        binder_length_min=binder_min,
        binder_length_max=binder_max,
        num_designs=num_designs,
    )
    click.echo(f"Wrote {output_yaml}")
    click.echo(f"hotspot_res: {result.rfdiffusion_hotspot_res}")
    click.echo(f"contig: {result.contig_template}")


@main.command("validate")
@click.argument("structure_path", type=click.Path(exists=True))
@click.option("--peptide-chain", default=None)
@click.option("--hla-chain", default=None)
def validate_cmd(structure_path, peptide_chain, hla_chain):
    """Validate a pMHC structure without scoring."""
    from pmhc_hotspot.io import StructureLoader
    from pmhc_hotspot.validation import StructureValidator

    structure = StructureLoader().load(structure_path)
    report = StructureValidator().validate(structure, peptide_chain, hla_chain)
    if report.errors:
        click.echo("ERRORS:", err=True)
        for e in report.errors:
            click.echo(f"  - {e}", err=True)
    if report.warnings:
        click.echo("WARNINGS:")
        for w in report.warnings:
            click.echo(f"  - {w}")
    if report.ok and not report.warnings:
        click.echo("Structure validation passed.")
    elif report.ok:
        click.echo("Structure validation passed with warnings.")


if __name__ == "__main__":
    main()
