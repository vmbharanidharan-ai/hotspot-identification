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


@main.command("benchmark")
@click.option(
    "--manifest",
    "manifest_path",
    default=None,
    help="Benchmark manifest YAML (default: bundled 15-structure set)",
)
@click.option("--allele", default=None, help="Override allele for all structures")
@click.option("--download/--no-download", default=False, help="Download missing PDBs via PDBList")
@click.option("--cache-dir", default="data/pdb", show_default=True)
@click.option("--out", "out_json", default="benchmark_report.json", show_default=True)
def benchmark_cmd(manifest_path, allele, download, cache_dir, out_json):
    """Run TCR-contact recovery benchmark over curated structures."""
    predictor = HotspotPredictor(allele=allele)
    report = predictor.benchmark(
        manifest_path,
        download=download,
        cache_dir=cache_dir,
    )
    with open(out_json, "w") as fh:
        json.dump(report, fh, indent=2)
    click.echo(f"Wrote {out_json}")
    summary = report.get("summary", {})
    click.echo(f"Structures evaluated: {summary.get('n_structures', 0)}")
    if summary.get("n_structures"):
        click.echo(f"Mean recall@5: {summary.get('mean_recall_at_5', 0):.3f}")
        click.echo(f"Mean anchor avoidance@5: {summary.get('mean_anchor_avoidance_at_5', 0):.3f}")


@main.command("ml-train")
@click.option("--manifest", "manifest_path", default=None)
@click.option("--download/--no-download", default=False)
@click.option("--model", "model_type", default="logistic", type=click.Choice(["logistic", "xgboost"]))
@click.option("--out", "out_json", default="ml_cv_report.json", show_default=True)
def ml_train_cmd(manifest_path, download, model_type, out_json):
    """Build training data from benchmark manifest and run grouped CV."""
    predictor = HotspotPredictor()
    df = predictor.build_ml_training_frame(manifest_path, download=download)
    if df.empty:
        raise click.ClickException("No training rows produced. Try --download or check manifest paths.")

    from pmhc_hotspot.ml.train import train_cv

    report = train_cv(df, model_type=model_type)
    with open(out_json, "w") as fh:
        json.dump(report, fh, indent=2)
    click.echo(f"Training rows: {report['n_rows']} (positives: {report['n_positive']})")
    click.echo(f"Overall ROC-AUC: {report['overall']['roc_auc']:.3f}")
    click.echo(f"Wrote {out_json}")


@main.command("ml-pretrain")
@click.option("--iedb", "iedb_path", type=click.Path(exists=True), default=None)
@click.option("--atlas", "atlas_path", type=click.Path(exists=True), default=None)
@click.option("--model", "model_type", default="logistic", type=click.Choice(["logistic", "xgboost"]))
@click.option("--out", "out_json", default="pretrain_report.json", show_default=True)
def ml_pretrain_cmd(iedb_path, atlas_path, model_type, out_json):
    """Stage 1: cross-validate on public IEDB/ATLAS-style binding data."""
    from pmhc_hotspot.data.public_datasets import combine_public_datasets, load_atlas_csv, load_iedb_csv
    from pmhc_hotspot.ml.pretrain import train_public_pretrain

    frames = []
    if iedb_path:
        frames.append(load_iedb_csv(iedb_path))
    if atlas_path:
        frames.append(load_atlas_csv(atlas_path))
    if not frames:
        raise click.ClickException("Provide --iedb and/or --atlas CSV paths")

    df = combine_public_datasets(frames)
    report = train_public_pretrain(df, model_type=model_type)
    with open(out_json, "w") as fh:
        json.dump({k: v for k, v in report.items() if k != "oof"}, fh, indent=2)
    click.echo(f"Public rows: {report['n_rows']} | ROC-AUC: {report['roc_auc']:.3f}")
    click.echo(f"Wrote {out_json}")


@main.command("ml-fine-tune")
@click.option("--manifest", "manifest_path", default=None)
@click.option("--download/--no-download", default=False)
@click.option("--iedb", "iedb_path", type=click.Path(exists=True), default=None)
@click.option("--atlas", "atlas_path", type=click.Path(exists=True), default=None)
@click.option("--model", "model_type", default="logistic", type=click.Choice(["logistic", "xgboost"]))
@click.option("--out", "out_json", default="finetune_report.json", show_default=True)
def ml_fine_tune_cmd(manifest_path, download, iedb_path, atlas_path, model_type, out_json):
    """Stage 2: fine-tune on structural TCR-contact residue labels."""
    from pmhc_hotspot.api import HotspotPredictor
    from pmhc_hotspot.data.public_datasets import combine_public_datasets, load_atlas_csv, load_iedb_csv
    from pmhc_hotspot.ml.fine_tune import attach_pretrain_probabilities, fine_tune_structural
    from pmhc_hotspot.ml.pretrain import fit_public_pretrain_model

    predictor = HotspotPredictor()
    structural = predictor.build_ml_training_frame(manifest_path, download=download)
    if structural.empty:
        raise click.ClickException("No structural training rows produced")

    public_frames = []
    if iedb_path:
        public_frames.append(load_iedb_csv(iedb_path))
    if atlas_path:
        public_frames.append(load_atlas_csv(atlas_path))

    use_pretrain = bool(public_frames)
    if use_pretrain:
        public_df = combine_public_datasets(public_frames)
        pretrained, _ = fit_public_pretrain_model(public_df, model_type=model_type)
        structural = attach_pretrain_probabilities(structural, pretrained)

    report = fine_tune_structural(
        structural,
        model_type=model_type,
        use_pretrain_feature=use_pretrain,
    )
    with open(out_json, "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    click.echo(f"Structural rows: {report['n_rows']} | ROC-AUC: {report['overall']['roc_auc']:.3f}")
    click.echo(f"Wrote {out_json}")


@main.command("ml-staged")
@click.option("--iedb", "iedb_path", type=click.Path(exists=True), required=True)
@click.option("--atlas", "atlas_path", type=click.Path(exists=True), default=None)
@click.option("--manifest", "manifest_path", default=None)
@click.option("--download/--no-download", default=False)
@click.option("--model", "model_type", default="logistic", type=click.Choice(["logistic", "xgboost"]))
@click.option("--out", "out_json", default="staged_training_report.json", show_default=True)
def ml_staged_cmd(iedb_path, atlas_path, manifest_path, download, model_type, out_json):
    """Run full two-stage training: public pretrain then structural fine-tune."""
    from pmhc_hotspot.api import HotspotPredictor
    from pmhc_hotspot.data.public_datasets import combine_public_datasets, load_atlas_csv, load_iedb_csv
    from pmhc_hotspot.ml.staged import run_staged_training

    frames = [load_iedb_csv(iedb_path)]
    if atlas_path:
        frames.append(load_atlas_csv(atlas_path))
    public_df = combine_public_datasets(frames)
    structural_df = HotspotPredictor().build_ml_training_frame(manifest_path, download=download)
    report = run_staged_training(public_df, structural_df, model_type=model_type)
    serializable = {
        "pretrain_cv": report["pretrain_cv"],
        "finetune_cv": report["finetune_cv"],
        "n_public_rows": report["n_public_rows"],
        "n_structural_rows": report["n_structural_rows"],
    }
    with open(out_json, "w") as fh:
        json.dump(serializable, fh, indent=2, default=str)
    click.echo(f"Pretrain ROC-AUC: {report['pretrain_cv']['roc_auc']:.3f}")
    click.echo(f"Finetune ROC-AUC: {report['finetune_cv']['overall']['roc_auc']:.3f}")
    click.echo(f"Wrote {out_json}")


if __name__ == "__main__":
    main()
