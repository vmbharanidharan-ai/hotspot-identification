# Methods (draft)

## Dataset
- STCRDab + RCSB crawl via `pmhc-hotspot expand-dataset`
- Contact labels: `ContactLabelGenerator` (standard mode, 4.5 Å)
- Holdout: `data/pdb/eval_set_expanded.yaml`

## Models
- **XGBoost**: grouped CV on residue features (`pmhc-hotspot ml-compare`)
- **GNN**: GraphSAGE (`HotspotGNN` in `ml/gnn_model.py`)
- **Hybrid**: average XGBoost + GNN scores

## Design validation
- Controls: hotspot, random, exposed, central (`design/control_strategies.py`)
- RFdiffusion batch: `pmhc-hotspot design`
- AF2 scoring: `pmhc-hotspot score-designs`

## Uncertainty
- Platt calibration + feature jitter (`uncertainty/confidence.py`)
