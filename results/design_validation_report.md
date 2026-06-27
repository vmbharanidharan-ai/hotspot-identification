# Design Validation Results (template — Phase 2.6)

## Question
Do pmhc-hotspot predictions improve RFdiffusion-designed binder quality?

## Methods
- Eval PDBs from `data/pdb/eval_set_expanded.yaml`
- Strategies: hotspot, random, exposed, central
- Metrics: interface pAE, interface RMSD, interface contacts, BSA

## Results
Populate after running:
```bash
pmhc-hotspot design --eval-manifest data/pdb/eval_set_expanded.yaml
pmhc-hotspot score --design-dir artifacts/design_outputs
pmhc-hotspot run-design-validation
```

## Statistical Significance
Report t-test / Mann-Whitney U from `validation_metrics.compare_strategies`.

## Failures
See `data/failures/analysis_summary.json`.

## Conclusion
Update after gatekeeper verdict.
