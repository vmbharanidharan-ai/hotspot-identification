# Design-conditioning interchange format (schema v1.0)

This file is the **contract** between pmhc-hotspot and design backends (RFdiffusion, ProteinMPNN, AF2).

## Example

```yaml
schema_version: "1.0"
target_id: 1BD2_HLA-A02-01
control_group: predicted
pdb_id: "1BD2"
allele: HLA-A*02:01
peptide:
  chain: C
  sequence: GILGFVFTL
hla_chains:
  - A
hotspots:
  - residue: 4
    position: P4
    confidence: 0.93
    patch_id: A
    chain: C
  - residue: 5
    position: P5
    confidence: 0.88
    patch_id: A
    chain: C
patches:
  - id: A
    center: 4
    radius: 6.0
    normal: [0.1, 0.8, -0.6]
    members: [4, 5, 7]
    confidence: 0.91
rfdiffusion:
  hotspot_res: "C4,C5,C7"
  contigs: "C1-9/0 A1-275/0 50-80"
  num_designs: 100
  seed: 42
scoring_mode: hybrid
```

## Control groups

| `control_group` | Meaning |
|-----------------|--------|
| `random` | Random eligible residues |
| `exposed_only` | Highest SASA |
| `central_only` | Central bulge (P3–P8) |
| `predicted` | pmhc-hotspot output |

## Pydantic model

`pmhc_hotspot.schema.conditioning.DesignConditioning`

## Paths

```
artifacts/design_inputs/{target_id}/{control_group}.yaml
```
