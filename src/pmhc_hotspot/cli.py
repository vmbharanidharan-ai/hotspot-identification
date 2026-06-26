"""Command-line interface for pmhc-hotspot."""

from __future__ import annotations

import json
from pathlib import Path

import click

from pmhc_hotspot.api import HotspotPredictor
from pmhc_hotspot.explain import format_explanation
from pmhc_hotspot.export import export_rfdiffusion_template, to_json, to_tsv
from pmhc_hotspot.features.mutation import MutationScorer


def _write_json(path: str, payload, **kwargs) -> None:
    out = Path(path)
    if out.parent != Path("."):
        out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as fh:
        json.dump(payload, fh, **kwargs)


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
@click.option(
    "--contact-mode",
    default="standard",
    show_default=True,
    type=click.Choice(["strict", "standard", "permissive"]),
    help="TCR-contact ground-truth definition for benchmark labels",
)
@click.option(
    "--scoring-mode",
    default="deterministic",
    show_default=True,
    type=click.Choice(["deterministic", "statistical", "ml", "hybrid"]),
    help="Residue ranking mode for benchmark evaluation",
)
@click.option(
    "--ml-bundle",
    default=None,
    type=click.Path(exists=True),
    help="Saved staged model bundle (.joblib) for ml/hybrid scoring",
)
@click.option("--out", "out_json", default="benchmark_report.json", show_default=True)
def benchmark_cmd(
    manifest_path, allele, download, cache_dir, contact_mode, scoring_mode, ml_bundle, out_json
):
    """Run TCR-contact recovery benchmark over curated structures."""
    from pmhc_hotspot.ml.persistence import resolve_default_model_bundle, resolve_model_bundle_path

    if scoring_mode in {"ml", "hybrid", "statistical"} and not ml_bundle:
        ml_bundle = str(resolve_model_bundle_path())
    predictor = HotspotPredictor(allele=allele, ml_bundle=ml_bundle, scoring_mode=scoring_mode)
    report = predictor.benchmark(
        manifest_path,
        download=download,
        cache_dir=cache_dir,
        contact_mode=contact_mode,
        scoring_mode=scoring_mode,
        ml_bundle=ml_bundle,
    )
    _write_json(out_json, report, indent=2)
    click.echo(f"Wrote {out_json}")
    summary = report.get("summary", {})
    click.echo(f"Structures evaluated: {summary.get('n_structures', 0)}")
    if summary.get("n_structures"):
        click.echo(f"Contact mode: {report.get('contact_mode', contact_mode)}")
        click.echo(f"Scoring mode: {report.get('scoring_mode', scoring_mode)}")
        click.echo(f"Mean recall@5: {summary.get('mean_recall_at_5', 0):.3f}")
        click.echo(f"Mean anchor avoidance@5: {summary.get('mean_anchor_avoidance_at_5', 0):.3f}")
        buried = summary.get("mean_buried_anchor_avoidance_at_5")
        if buried == buried:
            click.echo(f"Mean buried-anchor avoidance@5: {buried:.3f}")


@main.command("ml-train")
@click.option("--manifest", "manifest_path", default=None)
@click.option("--download/--no-download", default=False)
@click.option("--cache-dir", default="data/pdb", show_default=True, help="PDB download cache")
@click.option("--model", "model_type", default="logistic", type=click.Choice(["logistic", "xgboost"]))
@click.option(
    "--contact-mode",
    default="standard",
    show_default=True,
    type=click.Choice(["strict", "standard", "permissive"]),
    help="TCR-contact label definition when building training rows",
)
@click.option("--out", "out_json", default="ml_cv_report.json", show_default=True)
def ml_train_cmd(manifest_path, download, cache_dir, model_type, contact_mode, out_json):
    """Build training data from benchmark manifest and run grouped CV."""
    predictor = HotspotPredictor()
    df = predictor.build_ml_training_frame(
        manifest_path,
        download=download,
        contact_mode=contact_mode,
        cache_dir=cache_dir,
    )
    if df.empty:
        raise click.ClickException("No training rows produced. Try --download or check manifest paths.")

    from pmhc_hotspot.ml.train import train_cv

    report = train_cv(df, model_type=model_type)
    _write_json(out_json, report, indent=2)
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
    _write_json(out_json, {k: v for k, v in report.items() if k != "oof"}, indent=2)
    click.echo(f"Public rows: {report['n_rows']} | ROC-AUC: {report['roc_auc']:.3f}")
    click.echo(f"Wrote {out_json}")


@main.command("ml-fine-tune")
@click.option("--manifest", "manifest_path", default=None)
@click.option("--download/--no-download", default=False)
@click.option("--cache-dir", default="data/pdb", show_default=True, help="PDB download cache")
@click.option("--iedb", "iedb_path", type=click.Path(exists=True), default=None)
@click.option("--atlas", "atlas_path", type=click.Path(exists=True), default=None)
@click.option("--model", "model_type", default="logistic", type=click.Choice(["logistic", "xgboost"]))
@click.option(
    "--contact-mode",
    default="standard",
    show_default=True,
    type=click.Choice(["strict", "standard", "permissive"]),
)
@click.option("--out", "out_json", default="finetune_report.json", show_default=True)
def ml_fine_tune_cmd(
    manifest_path, download, cache_dir, iedb_path, atlas_path, model_type, contact_mode, out_json
):
    """Stage 2: fine-tune on structural TCR-contact residue labels."""
    from pmhc_hotspot.api import HotspotPredictor
    from pmhc_hotspot.data.public_datasets import combine_public_datasets, load_atlas_csv, load_iedb_csv
    from pmhc_hotspot.ml.fine_tune import attach_pretrain_probabilities, fine_tune_structural
    from pmhc_hotspot.ml.pretrain import fit_public_pretrain_model

    predictor = HotspotPredictor()
    structural = predictor.build_ml_training_frame(
        manifest_path,
        download=download,
        contact_mode=contact_mode,
        cache_dir=cache_dir,
    )
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
    _write_json(out_json, report, indent=2, default=str)
    click.echo(f"Structural rows: {report['n_rows']} | ROC-AUC: {report['overall']['roc_auc']:.3f}")
    click.echo(f"Wrote {out_json}")


@main.command("ml-staged")
@click.option("--iedb", "iedb_path", type=click.Path(exists=True), default=None)
@click.option("--atlas", "atlas_path", type=click.Path(exists=True), default=None)
@click.option("--manifest", "manifest_path", default=None)
@click.option("--download/--no-download", default=False)
@click.option("--cache-dir", default="data/pdb", show_default=True, help="PDB download cache")
@click.option("--model", "model_type", default="logistic", type=click.Choice(["logistic", "xgboost"]))
@click.option(
    "--contact-mode",
    default="standard",
    show_default=True,
    type=click.Choice(["strict", "standard", "permissive"]),
)
@click.option(
    "--save-model",
    default=None,
    type=click.Path(),
    help="Write staged model bundle (.joblib) for inference/benchmark",
)
@click.option("--no-pretrain", is_flag=True, help="Skip stage-1 public pretrain (ablation)")
@click.option("--no-calibrate", is_flag=True, help="Disable Platt calibration on ML/statistical models")
@click.option("--out", "out_json", default="staged_training_report.json", show_default=True)
def ml_staged_cmd(
    iedb_path,
    atlas_path,
    manifest_path,
    download,
    cache_dir,
    model_type,
    contact_mode,
    save_model,
    no_pretrain,
    no_calibrate,
    out_json,
):
    """Run full two-stage training: public pretrain then structural fine-tune."""
    from pmhc_hotspot.api import HotspotPredictor
    from pmhc_hotspot.data.public_datasets import combine_public_datasets, load_atlas_csv, load_iedb_csv
    from pmhc_hotspot.ml.persistence import save_staged_bundle
    from pmhc_hotspot.ml.staged import run_staged_training

    public_df = None
    if not no_pretrain:
        if not iedb_path:
            raise click.ClickException("--iedb is required unless --no-pretrain is set")
        frames = [load_iedb_csv(iedb_path)]
        if atlas_path:
            frames.append(load_atlas_csv(atlas_path))
        public_df = combine_public_datasets(frames)
    else:
        import pandas as pd

        public_df = pd.DataFrame()

    structural_df = HotspotPredictor().build_ml_training_frame(
        manifest_path,
        download=download,
        contact_mode=contact_mode,
        cache_dir=cache_dir,
    )
    report = run_staged_training(
        public_df,
        structural_df,
        model_type=model_type,
        contact_mode=contact_mode,
        use_pretrain=not no_pretrain,
        calibrate=not no_calibrate,
    )
    if save_model:
        save_staged_bundle(save_model, report["model_bundle"])
        click.echo(f"Saved model bundle: {save_model}")

    serializable = {
        "pretrain_cv": report["pretrain_cv"],
        "statistical_cv": {
            k: v for k, v in report["statistical_cv"].items() if k != "oof_predictions"
        },
        "finetune_cv": report["finetune_cv"],
        "hybrid_alpha": report["hybrid_alpha"],
        "n_public_rows": report["n_public_rows"],
        "n_structural_rows": report["n_structural_rows"],
        "contact_mode": report["contact_mode"],
        "use_pretrain": report["use_pretrain"],
        "calibrated": report["calibrated"],
        "model_saved": bool(save_model),
    }
    _write_json(out_json, serializable, indent=2, default=str)
    if report["pretrain_cv"]:
        click.echo(f"Pretrain ROC-AUC: {report['pretrain_cv']['roc_auc']:.3f}")
    click.echo(
        f"Statistical ROC-AUC: {report['statistical_cv']['overall']['roc_auc']:.3f}"
    )
    click.echo(f"Finetune ROC-AUC: {report['finetune_cv']['overall']['roc_auc']:.3f}")
    click.echo(f"Learned hybrid α (stat vs ML): {report['hybrid_alpha']:.3f}")
    click.echo(f"Wrote {out_json}")


@main.command("ml-holdout")
@click.option("--iedb", "iedb_path", type=click.Path(exists=True), required=True)
@click.option("--atlas", "atlas_path", type=click.Path(exists=True), default=None)
@click.option("--manifest", "manifest_path", default=None)
@click.option("--download/--no-download", default=False)
@click.option("--cache-dir", default="data/pdb", show_default=True, help="PDB download cache")
@click.option("--model", "model_type", default="xgboost", type=click.Choice(["logistic", "xgboost"]))
@click.option(
    "--contact-mode",
    default="standard",
    show_default=True,
    type=click.Choice(["strict", "standard", "permissive"]),
)
@click.option(
    "--scoring-mode",
    default="hybrid",
    show_default=True,
    type=click.Choice(["deterministic", "statistical", "ml", "hybrid"]),
)
@click.option(
    "--hold-out",
    "hold_out",
    multiple=True,
    required=True,
    help="PDB IDs to exclude from training and evaluate (repeatable)",
)
@click.option("--save-model", default=None, type=click.Path())
@click.option("--out", "out_json", default="holdout_report.json", show_default=True)
def ml_holdout_cmd(
    iedb_path,
    atlas_path,
    manifest_path,
    download,
    cache_dir,
    model_type,
    contact_mode,
    scoring_mode,
    hold_out,
    save_model,
    out_json,
):
    """Leave-structures-out validation with optional held-out benchmark."""
    from pmhc_hotspot.api import HotspotPredictor
    from pmhc_hotspot.benchmark.holdout import run_leave_structures_out
    from pmhc_hotspot.data.public_datasets import combine_public_datasets, load_atlas_csv, load_iedb_csv

    frames = [load_iedb_csv(iedb_path)]
    if atlas_path:
        frames.append(load_atlas_csv(atlas_path))
    public_df = combine_public_datasets(frames)
    structural_df = HotspotPredictor().build_ml_training_frame(
        manifest_path,
        download=download,
        contact_mode=contact_mode,
        cache_dir=cache_dir,
    )
    report = run_leave_structures_out(
        public_df,
        structural_df,
        list(hold_out),
        manifest_path=manifest_path,
        model_type=model_type,
        contact_mode=contact_mode,
        scoring_mode=scoring_mode,
        save_model_path=save_model,
        download=download,
        cache_dir=cache_dir,
    )
    _write_json(out_json, report, indent=2, default=str)
    summary = report["held_out_benchmark"]["summary"]
    click.echo(f"Held out: {', '.join(report['held_out'])}")
    if summary.get("n_structures"):
        click.echo(f"Held-out recall@5 ({scoring_mode}): {summary.get('mean_recall_at_5', 0):.3f}")
    click.echo(f"Wrote {out_json}")


@main.command("build-dataset")
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True),
    default="configs/dataset.yaml",
    show_default=True,
    help="Dataset build YAML config",
)
@click.option("--download/--no-download", default=None, help="Override config download flag")
@click.option(
    "--stcrdab",
    type=click.Path(exists=True),
    default=None,
    help="STCRDab summary TSV (adds stcrdab source)",
)
@click.option(
    "--processed-dir",
    type=click.Path(),
    default=None,
    help="Output directory for ComplexExample JSON",
)
def build_dataset_cmd(config_path, download, stcrdab, processed_dir):
    """Phase 1 ingest: build ComplexExample JSON from PDB manifests."""
    from pmhc_hotspot.preprocess import DatasetBuildConfig, build_dataset

    cfg = DatasetBuildConfig.from_yaml(config_path)
    if download is not None:
        cfg.download = download
    if stcrdab:
        cfg.stcrdab_path = Path(stcrdab)
        if "stcrdab" not in cfg.sources:
            cfg.sources.append("stcrdab")
    if processed_dir:
        cfg.processed_dir = Path(processed_dir)

    report = build_dataset(cfg)
    click.echo(f"Built {len(report.built)} examples → {cfg.processed_dir}/examples/")
    click.echo(f"Skipped {len(report.skipped)} structures")
    click.echo(f"Manifest: {cfg.output_manifest}")
    if report.skipped:
        for row in report.skipped[:5]:
            click.echo(f"  skip {row.get('pdb_id')}: {row.get('error')}", err=True)


@main.command("export-design")
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True),
    default="configs/design.yaml",
    show_default=True,
    help="Design export YAML config",
)
@click.option(
    "--output-dir",
    type=click.Path(),
    default=None,
    help="Override artifacts/design_inputs output directory",
)
def export_design_cmd(config_path, output_dir):
    """M5: export design-conditioning YAML for all control groups."""
    from pmhc_hotspot.design import DesignExportConfig, export_design_inputs

    cfg = DesignExportConfig.from_yaml(config_path)
    if output_dir:
        cfg.output_dir = Path(output_dir)

    report = export_design_inputs(cfg)
    click.echo(f"Exported {len(report.exported)} files → {cfg.output_dir}/")
    click.echo(f"Skipped {len(report.skipped)} targets")
    if report.skipped:
        for row in report.skipped[:5]:
            click.echo(f"  skip {row.get('example_id')}: {row.get('error')}", err=True)


if __name__ == "__main__":
    main()
