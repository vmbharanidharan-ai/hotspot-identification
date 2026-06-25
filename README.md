# pmhc-hotspot

**Structure- and immunology-informed hotspot selection for peptide–MHC binder design**

[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`pmhc-hotspot` is a pip- and conda-installable Python package that selects biologically meaningful hotspot residues on peptide–MHC (pMHC) complexes for [RFdiffusion](https://github.com/RosettaCommons/RFdiffusion) PPI binder design.

It fills the missing middle layer in the design pipeline:

```
structure → (manual guesswork) → RFdiffusion hotspots → RFdiffusion
                    ↓
structure → pmhc-hotspot → ranked residues + patches + RFdiffusion export → RFdiffusion
```

> **Important:** This is a **heuristic design-prioritization** tool, not a predictor of T-cell activation, immunogenicity, or binding affinity. Scores rank residues for *generative binder targeting*, informed by structural exposure, MHC anchor biology, and interface geometry.

---

## Table of contents

- [Why this package exists](#why-this-package-exists)
- [Biological rationale](#biological-rationale)
- [Features](#features)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Python API](#python-api)
- [CLI reference](#cli-reference)
- [Scoring method](#scoring-method)
- [RFdiffusion integration](#rfdiffusion-integration)
- [Output formats](#output-formats)
- [Benchmarking](#benchmarking)
- [Project structure](#project-structure)
- [Development](#development)
- [Citation](#citation)
- [License](#license)

---

## Why this package exists

Existing tools address **parts** of the problem but not the full design workflow:

| Tool class | Examples | What they do | Gap |
|------------|----------|--------------|-----|
| Structure utilities | PyMOL, DSSP, FreeSASA | Visualization, SASA | No hotspot inference |
| MHC binding predictors | NetMHCpan, MHCflurry | Peptide–MHC affinity | Not structural hotspots |
| TCR modeling | TCRFlexDock, etc. | TCR–pMHC docking | Not RFdiffusion-ready design targets |
| Generative design | RFdiffusion | Consumes `ppi.hotspot_res` | **Does not generate hotspots** |

`pmhc-hotspot` is the first open, explainable package focused on **pMHC-specific, RFdiffusion-ready hotspot selection** with allele-aware immunology built in.

---

## Biological rationale

Hotspot selection for pMHC binder design must respect three **distinct** concepts (not a single "exposure" score):

### 1. MHC-I anchor residues (allele-dependent)

Class I peptides bind via N-terminal (P2) and C-terminal (PΩ) anchors that sit in the MHC groove. These positions are poor RFdiffusion targets when buried. The package uses a **curated allele table** (HLA-A\*02:01, A\*24:02, B\*44:02, etc.) with **multiplicative suppression** when anchors are buried.

### 2. TCR-facing exposure

TCRs recognize a conformational footprint spanning central peptide residues (often P3–P8) and some MHC α-helical residues. Central **bulge/protrusion** geometry can mark TCR-contacted positions even when absolute SASA is moderate.

### 3. Peptide stabilization & designability

Proline and glycine are deprioritized (rigid or too flexible for PPI hotspots). Final hotspot sets require **≥3 hydrophobic residues** (W/F/Y/M/L/I/V/C), consistent with RFdiffusion PPI interface guidelines.

### What we explicitly do *not* claim

- Mutation proximity is a **soft bias**, not proof of immunogenicity
- High SASA alone does not define a good hotspot
- Scores are structure-quality-dependent (low pLDDT/B-factor regions are downweighted)

---

## Features

- **Deterministic baseline scorer** — no ML required for v0.1
- **Variable peptide length** — 8–15 residues (not hardcoded to 9-mers)
- **Normalized, explainable features** — every score decomposes into weighted components
- **Contiguous patch selection** — spatially coherent targets for RFdiffusion
- **RFdiffusion export** — `ppi.hotspot_res` tokens, contig template, YAML helper
- **Structure validation** — chain detection, missing atoms, altloc warnings
- **CLI + Python API** — same logic in both interfaces
- **JSON + TSV export** — human-readable and machine-consumable
- **Benchmarking scaffold** — TCR-contact recovery, anchor avoidance, patch contiguity

---

## Installation

### pip (recommended)

```bash
git clone https://github.com/vmbharanidharan-ai/hotspot-identification.git
cd hotspot-identification
pip install -e .
```

With development dependencies:

```bash
pip install -e ".[dev]"
```

### conda

```bash
conda env create -f environment.yml
conda activate pmhc-hotspot
```

Or build from the included recipe:

```bash
conda build conda/
```

### Optional ML extras (Phase 2)

```bash
pip install -e ".[ml]"
```

---

## Quick start

### CLI

```bash
# Score hotspots and write TSV + optional JSON
pmhc-hotspot run complex.pdb --allele HLA-A*02:01 --out hotspots.tsv --json-out hotspots.json

# Per-residue explanation
pmhc-hotspot explain complex.pdb --allele HLA-A*02:01

# Export RFdiffusion template
pmhc-hotspot export-rfdiffusion complex.pdb design_config.yaml

# Validate structure only
pmhc-hotspot validate complex.pdb
```

### Python

```python
from pmhc_hotspot import HotspotPredictor

predictor = HotspotPredictor(
    allele="HLA-A*02:01",
    mutation_positions=[4],  # 0-based index; P5 in 1-based notation
)

result = predictor.predict("complex.pdb")

print(result.peptide_sequence)
print(result.rfdiffusion_hotspot_res)   # e.g. "P4,P5,P6,P7,P8"
print(result.contig_template)           # e.g. "P1-9/0 H1-20/0 50-80"

for r in result.hotspots:
    print(r.position, r.aa, f"{r.score:.3f}", r.explanation)
```

---

## Python API

### `HotspotPredictor`

| Parameter | Type | Description |
|-----------|------|-------------|
| `allele` | `str \| None` | HLA allele (`HLA-A*02:01`, `HLA-A02:01`, etc.) |
| `mutation_positions` | `list[int]` | 0-based peptide indices with somatic mutations |
| `weights` | `dict` | Override default feature weights |
| `peptide_chain` | `str \| None` | Force peptide chain ID (auto-detect if `None`) |
| `hla_chain` | `str \| None` | Force HLA chain ID |
| `hotspot_config` | `dict` | `min_hotspots`, `max_hotspots`, `min_hydrophobic`, etc. |

### `PredictionResult`

| Field | Description |
|-------|-------------|
| `residue_scores` | All peptide residues, ranked by score |
| `hotspots` | Final RFdiffusion hotspot set (5–6 residues, biologically filtered) |
| `patches` | Contiguous high-scoring surface patches |
| `rfdiffusion_hotspot_res` | Comma-separated `ChainResnum` tokens |
| `contig_template` | RFdiffusion contig string fixing peptide + HLA |
| `metadata` | Warnings, anchor positions, method version |

---

## CLI reference

```
pmhc-hotspot run STRUCTURE [--allele ALLELE] [--mutation P5] [--out FILE] [--json-out FILE]
pmhc-hotspot explain STRUCTURE [--allele ALLELE]
pmhc-hotspot export-rfdiffusion STRUCTURE OUTPUT.yaml [--binder-min N] [--binder-max N]
pmhc-hotspot validate STRUCTURE
```

---

## Scoring method

### Pipeline

1. Load PDB/mmCIF (Biopython)
2. Validate structure and infer peptide/HLA chains
3. Map residues to P1–Pn with normalized position (0–1)
4. Compute per-residue features
5. **Min-max normalize** features within the peptide (critical for cross-structure comparability)
6. Weighted linear combination → base score
7. **Multiplicative anchor penalty** for buried anchor residues
8. Select contiguous patches and final RFdiffusion hotspot set

### Features (Phase 1)

| Feature | Biological role |
|---------|-----------------|
| Relative SASA | Solvent exposure / TCR accessibility proxy |
| Protrusion | Local convexity above peptide neighborhood |
| Curvature | Backbone deviation at residue |
| Bulge | Cα displacement from local backbone (central bulge) |
| HLA contact burden | Burial in MHC groove (inverted in score) |
| TCR exposure prior | Central position + favorable chemistry (W/R/Y/F/K) |
| Mutation proximity | Soft neoantigen bias (optional) |
| Confidence | Downweight low pLDDT / high B-factor regions |
| Chemical score | Interface hotspot hierarchy from alanine-scanning literature |

### Baseline formula

```
base = Σ (weight_i × normalized_feature_i)
final_score = clamp(base × (1 − anchor_penalty), 0, 1)
```

Default weights are in `pmhc_hotspot/constants.py` and can be overridden.

### Final hotspot selection rules

- Skip allele anchor positions (when buried)
- Skip Pro, Gly; skip N-terminal Ala/Gly
- Select 5–6 contiguous central residues when possible
- Require ≥3 hydrophobic residues in final set

---

## RFdiffusion integration

The package exports three artifacts:

### 1. `ppi.hotspot_res` string

Comma-separated chain+residue tokens matching RFdiffusion PPI convention:

```
P4,P5,P6,P7,P8
```

### 2. Contig template

Fixes peptide and HLA chains, defines binder length range:

```
P1-9/0 H1-275/0 50-80
```

### 3. YAML config template

Minimal helper (verify against your RFdiffusion version):

```yaml
ppi:
  hotspot_res: P4,P5,P6,P7,P8
  target_chains: [H]
contigmap:
  contigs: P1-9/0 H1-275/0 50-80
  num_designs: 100
```

> RFdiffusion config formats evolve. Treat the YAML export as a **versioned template**, not a guaranteed drop-in for all releases.

---

## Output formats

### TSV

Tab-separated per-residue table with scores, features, and JSON-encoded explanations.

### JSON

Full `PredictionResult` serialization including patches, metadata, and provenance — suitable for downstream pipelines.

---

## Benchmarking

A scaffold is included for three evaluation axes:

1. **TCR-contact recovery** — overlap with known TCR-contacted peptide positions in PDB complexes
2. **Anchor avoidance** — fraction of predictions avoiding MHC anchor positions
3. **Patch contiguity** — spatial coherence of selected hotspots

```python
from pmhc_hotspot.benchmarking.dataset import PDBDataset
from pmhc_hotspot.benchmarking.metrics import HotspotEvaluator

dataset = PDBDataset()
paths = dataset.download_all()  # curated PDB IDs
```

Curated benchmark IDs: `1A6Z`, `2C5L`, `3GHW`, `2VLJ`, `5NHT`, `5NM8`.

---

## Project structure

```
hotspot-identification/
├── src/pmhc_hotspot/          # Main package
│   ├── api.py                 # HotspotPredictor (public API)
│   ├── cli.py                 # Command-line interface
│   ├── types.py               # ResidueScore, HotspotPatch, PredictionResult
│   ├── features/              # SASA, geometry, contacts, allele rules
│   ├── scoring/               # Baseline scorer, patches, selection
│   └── benchmarking/          # Dataset + metrics scaffold
├── tests/                     # Unit + integration tests
├── examples/                  # Example inputs
├── conda/meta.yaml            # Conda recipe
├── pyproject.toml             # pip/Hatch packaging
└── environment.yml            # Conda development environment
```

---

## Development

```bash
# Install in editable mode with dev tools
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=pmhc_hotspot --cov-report=term-missing

# Lint
ruff check src tests
black --check src tests
```

### Roadmap

| Phase | Status | Content |
|-------|--------|---------|
| **1** | ✅ v0.1.0 | Deterministic scorer, patches, RFdiffusion export, CLI |
| **2** | Planned | Full benchmark on 10+ TCR-bound pMHC structures |
| **3** | Optional | XGBoost layer trained on TCR-contact labels |

---

## Citation

If you use `pmhc-hotspot` in research, please cite:

```bibtex
@software{pmhc_hotspot2026,
  title  = {pmhc-hotspot: Structure-aware hotspot selection for peptide-MHC binder design},
  author = {Bharanidharan, Vedha},
  year   = {2026},
  url    = {https://github.com/vmbharanidharan-ai/hotspot-identification}
}
```

### Key references

- Rudolph, M. G. et al. Crystal structures of MHC-I/peptide/TCR complexes — anchor and TCR footprint biology
- Tien, M. Z. et al. (2013) Maximum accessible surface area benchmarks for relative SASA
- Watson, J. L. et al. (2023) RFdiffusion — generative protein design with PPI hotspot conditioning
- NetMHCpan motif tables — allele-specific anchor position curation

---

## License

MIT License — see [LICENSE](LICENSE).
