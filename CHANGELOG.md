# Changelog

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
