# Accurate Hotspot Prediction for Immunogenic TCR–pMHC Interface Design via Graph Neural Networks

## Abstract (draft)
Hotspot prediction improves designed binder quality. We introduce a benchmark dataset (30 structures), a GNN that fuses structure and sequence binding signals, and an open-source tool.

## Introduction
TCR binder design requires predicting which peptide residues interact with the TCR. Structure-only heuristics generalize poorly; ML on expanded datasets with design validation addresses this gap.

## Results (outline)
1. **Design validation (Tier 2.5)** — RFdiffusion + hotspots vs. controls (`results/design_validation_report.md`)
2. **GNN (Tier 4a)** — GraphSAGE with multi-signal node features (`src/pmhc_hotspot/ml/gnn_*.py`)
3. **Benchmark** — `data/pmhc_hotspot_benchmark/`

## Methods
- Dataset: ~277 training, 30 eval (after `expand-dataset`)
- GNN: GraphSAGE, multi-modal node features
- Design: RFdiffusion + AF2 interface scoring

## Figures
- `paper/figures/` — populate after HPC runs

## Code
https://github.com/vmbharanidharan-ai/hotspot-identification
