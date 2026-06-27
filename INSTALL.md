# Installation & Usage

## Quick start

```bash
git clone https://github.com/vmbharanidharan-ai/hotspot-identification.git
cd hotspot-identification
pip install -e ".[dev,schema,ml]"
```

## Predict hotspots

```bash
pmhc-hotspot predict examples/minimal_pmhc.pdb \
  --allele HLA-A*02:01 \
  --peptide-chain P --hla-chain H \
  --model hybrid \
  --with-uncertainty \
  --output results/prediction.yaml
```

## Reproduce benchmark results

1. Download benchmark structures into `data/pmhc_hotspot_benchmark/structures/`
2. Run `pmhc-hotspot benchmark --manifest data/pmhc_hotspot_benchmark/benchmark_split.yaml`
3. Compare to `data/pmhc_hotspot_benchmark/leaderboard.md`

## Optional extras

| Extra | Install |
|-------|---------|
| GNN training | `pip install -e ".[gnn]"` + [torch-geometric](https://pytorch-geometric.readthedocs.io) |
| Schema validation | `pip install -e ".[schema]"` |
| Cursor SDK automation | `pip install cursor-sdk` + `CURSOR_API_KEY` |

See `docs/FULL_PIPELINE_RUNBOOK.md` for Longleaf HPC steps.
