# Changelog

## 0.3.0 — 2026-06-25

- Two-stage ML: public IEDB/ATLAS pretraining + structural fine-tuning
- `data/public_datasets.py` with validated CSV loaders (user-provided exports only)
- `ml/pretrain.py`, `ml/fine_tune.py`, `ml/hybrid.py`, `ml/staged.py`
- CLI: `ml-pretrain`, `ml-fine-tune`, `ml-staged`
- Safer PDB downloads (ID validation, cache path checks)
- Pinned dependencies, NOTICE file, environment-lock.yml, conda CLI test

## 0.2.0 — 2026-06-25

- Benchmark runner over 15 curated TCR-bound pMHC structures (Biopython PDBList download)
- TCR-contact recovery, anchor avoidance, and patch contiguity metrics
- Optional ML scaffold: feature matrix, XGBoost/logistic pipelines, grouped CV training
- `low_confidence` residue flag for cleaner ML labels
- CLI: `benchmark`, `ml-train`
- PyPI/conda-forge publishing docs and GitHub Actions CI/release workflows

## 0.1.0 — 2026-06-25

Initial public release.

- Deterministic, explainable hotspot scoring for peptide–MHC complexes
- Variable peptide length support (8–15 residues)
- Allele-aware anchor suppression with curated MHC-I rules
- Structure features: relative SASA, protrusion, curvature, bulge, contacts
- Contiguous patch selection and RFdiffusion-ready export
- CLI (`pmhc-hotspot`) and Python API (`HotspotPredictor`)
- JSON and TSV export with per-residue explanations
- Benchmarking scaffold for TCR-contact recovery metrics
