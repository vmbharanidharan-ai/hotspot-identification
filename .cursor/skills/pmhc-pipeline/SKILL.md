---
name: pmhc-pipeline
description: >-
  Run the pmhc-hotspot binder-conditioning pipeline: Phase 1 ingest, Cursor
  orchestrator/agents, configs, and SDK automation. Use when working on
  preprocess/, run_pipeline.py, design export, or agent-driven milestones M1–M7.
---
# pmhc-hotspot binder-conditioning pipeline

## Quick commands

```bash
pmhc-hotspot build-dataset --config configs/dataset.yaml
pmhc-hotspot compute-features --config configs/features.yaml
pmhc-hotspot export-design --config configs/design.yaml
pmhc-hotspot run-design-validation --config configs/eval.yaml
python scripts/run_pipeline.py all
```

Full runbook: `docs/DESIGN_PIPELINE_RUNBOOK.md`  
Build spec: `pmhc-hotspot-dev-plan.md`

## API key

- **Ingest / IDE subagents:** no API key
- **SDK** (`scripts/launch_design_cycle.py`): `CURSOR_API_KEY` + `pip install cursor-sdk`

## Agent roles (`.cursor/agents/`)

| Phase | Agent | Allowed code areas |
|-------|-------|-------------------|
| ingest | ingest | `preprocess/`, `labels/`, ingest tests |
| features | feature | `features/`, feature matrix |
| design-export | design | `design/`, `patches/`, `artifacts/design_inputs/` |
| design-eval | eval | `eval/`, `artifacts/metrics/` |
| gatekeeper | gatekeeper | reports only, verdict JSON |
| full cycle | orchestrator | dispatch only, no science edits |

## Contracts

- `src/pmhc_hotspot/schema/examples.py` — `ComplexExample`
- `src/pmhc_hotspot/schema/conditioning.py` — RFdiffusion YAML
- `src/pmhc_hotspot/schema/design_eval.py` — validation report

## Orchestrator one-liner (IDE)

Ask in Agent chat:

> Use the orchestrator subagent to run one cycle per `pmhc-hotspot-dev-plan.md`, starting with ingest if examples are missing.
