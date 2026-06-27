# Nature Methods build runbook

This repo implements the 16-week plan from `pmhc_hotspot_cursor_instructions.md`.

## Quick start (no API keys)

```bash
cd ~/Projects/hotspot-identification
pip install -e ".[dev,schema,ml]"

# Phase 0 foundation
pmhc-hotspot crawl-pdb --pdb-id 1BD2 --pdb-id 3UTT
pmhc-hotspot label-contacts --pdb-dir data/pdb --workers 4
pmhc-hotspot run examples/minimal_pmhc.pdb --allele HLA-A*02:01 \
  --peptide-chain P --hla-chain H --with-uncertainty \
  --yaml-out artifacts/hotspot.yaml

# Full local pipeline skeleton
python scripts/run_nature_methods_pipeline.py pipeline
```

## API keys and external tools

| What | Required? | Where to set |
|------|-----------|--------------|
| **Cursor SDK agents** | Only for headless automation | `export CURSOR_API_KEY=...` from [cursor.com/dashboard](https://cursor.com/dashboard) |
| **RCSB PDB crawl** | No key | Public API |
| **RFdiffusion** | HPC install, not API key | `export RFDIFFUSION_BIN=/path/to/rfdiffusion` |
| **AlphaFold2 / ColabFold** | HPC install | `export AF2_BIN=colabfold_batch` |
| **AutoDock Vina** | Optional docking check | `export VINA_BIN=vina` |
| **NetMHCpan** | Optional sequence signal for GNN | Local install + `NETMHCPAN_HOME` |
| **STCRDab TSV** | Data file, not API | `configs/dataset.yaml` → `stcrdab.path` |

## GNN stack (Phase 3)

```bash
pip install -e ".[gnn]"
# torch-geometric: follow https://pytorch-geometric.readthedocs.io for your CUDA version
pmhc-hotspot ml-compare --config configs/baseline.yaml
```

## Longleaf HPC order

1. `pmhc-hotspot expand-dataset` (crawl + label)
2. `pmhc-hotspot build-dataset --stcrdab /path/to/STCRDab.tsv`
3. `pmhc-hotspot ml-compare --download`
4. `pmhc-hotspot design --eval-manifest data/pdb/eval_set_expanded.yaml`
5. `pmhc-hotspot score-designs --design-dir artifacts/design_outputs --mhc-pdb data/pdb/1BD2.pdb`
6. `pmhc-hotspot run-design-validation`

## Phase gates

- **Gate 0**: `pytest tests/test_phase0.py` passes; chain detection on eval PDBs
- **Gate 1**: `clean_structures_*.json` has ≥150 training structures
- **Gate 2**: `results/design_validation_report.md` — hotspots beat random (p<0.05)
- **Gate 3**: GNN recall@5 > 0.80 on expanded eval set

See `results/design_validation_report.md` and `data/pmhc_hotspot_benchmark/README.md`.
