# Design validation eval schema (schema v1.0)

Downstream validation compares **predicted** hotspot conditioning against control groups on the same target.

## Primary metrics (M6)

| Metric | Direction | Source |
|--------|-----------|--------|
| `af2_ipae` | lower better | AlphaFold2 multimer |
| `interface_pae` | lower better | AF2 / alignment |
| `interface_rmsd` | lower better | vs reference / re-dock |
| `interface_contacts` | higher better | Contact count at interface |
| `buried_surface_area` | context-dependent | Interface BSA |
| `rosetta_interface_score` | lower better | Rosetta interface |
| `hotspot_contact_fraction` | higher better | Designed binder contacts predicted hotspots |

Default primary: **`af2_ipae`**.

## Gate rule

**APPROVE_PROMOTE** only if `predicted` beats at least one control (`random`, `exposed_only`, or `central_only`) on the primary metric with pre-registered tolerance.

## Report file

`artifacts/metrics/{target_id}/ranking_report.json`

Pydantic: `pmhc_hotspot.schema.design_eval.DesignEvalReport`

## Example fragment

```json
{
  "schema_version": "1.0",
  "target_id": "1BD2_HLA-A02-01",
  "primary_metric": "af2_ipae",
  "higher_is_better": false,
  "comparisons": [
    {"control_group": "random", "n_candidates": 100, "primary_metric": "af2_ipae", "mean_primary": 12.4},
    {"control_group": "predicted", "n_candidates": 100, "primary_metric": "af2_ipae", "mean_primary": 8.1}
  ],
  "predicted_beats_controls": ["random", "exposed_only"],
  "gatekeeper_verdict": "APPROVE_PROMOTE"
}
```

## Experiment matrix

Per target, same `n_designs` and ranking pipeline for all four control groups.
