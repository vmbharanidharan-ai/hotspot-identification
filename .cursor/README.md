# Cursor agents — binder-conditioning pipeline

See **`pmhc-hotspot-dev-plan.md`** for milestones and orchestration.

| Subagent | Role |
|----------|------|
| `orchestrator` | Dispatch cycle; call gatekeeper |
| `ingest` | Structures → `ComplexExample` JSON |
| `feature` | Residue features |
| `model` | Train baseline / GNN |
| `design` | `DesignConditioning` YAML + RFdiffusion prep |
| `eval` | MPNN/AF2 metrics vs controls |
| `gatekeeper` | APPROVE_PROMOTE / REJECT / RETRY |
| `docking` | M3 geometry priors only (inactive until approved) |

Legacy numbered agents (`01_trainer` …) are superseded by this layout.

**Start a cycle:**

```
Use the orchestrator subagent to run one design-conditioning cycle per pmhc-hotspot-dev-plan.md
```

**Pipeline CLI:**

```bash
python scripts/run_pipeline.py design-export
```
