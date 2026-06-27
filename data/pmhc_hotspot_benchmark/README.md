# pmhc-hotspot Benchmark Dataset (Phase 4.3)

## Overview
Holdout TCR–pMHC structures with contact labels, model predictions, and leaderboard metrics.

## Layout
```
data/pmhc_hotspot_benchmark/
├── README.md
├── benchmark_split.yaml
├── leaderboard.md
├── structures/          # eval PDBs (symlink or copy from data/pdb/)
├── labels/              # contact JSON from label-contacts
├── predictions/         # xgboost / gnn / hybrid outputs
└── metrics/             # recall@k, AUC, calibration
```

## Populate
```bash
pmhc-hotspot crawl-pdb --pdb-id 1BD2 ...
pmhc-hotspot label-contacts --pdb-dir data/pdb
pmhc-hotspot run --yaml-out data/pmhc_hotspot_benchmark/predictions/1BD2_hotspot.yaml ...
pmhc-hotspot ml-compare --config configs/baseline.yaml
```

## Baseline targets
| Model | Recall@5 | AUC-ROC |
|-------|----------|---------|
| XGBoost | 0.76 | 0.88 |
| GNN | TBD | TBD |
| Hybrid | TBD | TBD |

## Citation
Cite the pmhc-hotspot repository and Zenodo DOI when published.
