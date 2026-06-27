# Designed TCR Binders for Experimental Testing (template — Phase 5.1)

## Summary
Populate after running:
```bash
pmhc-hotspot wetlab-candidates --eval-manifest data/pdb/eval_set_expanded.yaml --n 20
```

## Candidates

| ID | PDB | Peptide | Designed Seq | Hotspots | Confidence | AF2-PAE | Design Notes |
|----|-----|---------|--------------|----------|------------|---------|--------------|
| 1 | TBD | TBD | TBD | TBD | high | TBD | TBD |

## Wet Lab Strategy
1. Clone top-3 by confidence into mammalian expression vector
2. Measure binding kinetics (SPR or BIACORE) vs. wild-type TCR
3. Test biological activity (TCR transduction + activation assay)

## Success Criteria
- Binding affinity Kd < 10 μM
- At least 1/3 candidates bind better than WT control
- At least 1 candidate activates T cells

## Failure Mode Analysis
If designs don't bind:
- Check predicted hotspots vs. designed-structure contacts
- Check AF2 interface pAE (>0.5 suggests poor design)
- See `data/failures/analysis_summary.json`
