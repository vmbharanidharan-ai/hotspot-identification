# Agent automation loop

Nightly GitHub Actions workflows train, benchmark, gate, and optionally promote a champion model.
Cursor agents use the reports to propose **one bounded package patch per cycle**.

## Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `train.yml` | nightly 02:00 UTC, manual | `scripts/train_once.py` → artifacts |
| `benchmark.yml` | after train succeeds, manual | benchmark + biology + metrics gates |
| `agent-loop.yml` | manual | `scripts/generate_patch_brief.py` for Cursor |

## Agent roles (Cursor subagents)

Native subagents use YAML frontmatter in `.cursor/agents/`:

| `name` | File | Role |
|--------|------|------|
| `overnight-orchestrator` | `overnight-orchestrator.md` | Full cycle; launches parallel subagents |
| `analyst` | `analyst.md` | Diagnose bottleneck from reports |
| `biology-reviewer` | `biology-reviewer.md` | Biology pass/fail (parallel with analyst) |
| `patcher` | `patcher.md` | One minimal code fix + test |
| `reviewer` | `reviewer.md` | APPROVE / REJECT |
| `trainer` | `trainer.md` | Train only; no code edits |

Shared preamble: `.cursor/agents/00_shared_preamble.md`

**IDE parallel mode:** say `Use the overnight-orchestrator subagent` — Phase 2 delegates to `analyst` and `biology-reviewer` in one turn.

Full orchestration: **`pmhc-hotspot-dev-plan.md`** and **`AGENTS.md`**

# Overnight package-improvement loop

Package-first automation: improve **code** on the fixed 11-PDB eval manifest,
then optionally invoke Cursor agents to patch one subsystem per cycle.

## Quick start (Longleaf or local)

```bash
pip install -e ".[dev,ml,automation]"

# Automated agents (requires Cursor API key):
export CURSOR_API_KEY=...
bash scripts/run_overnight_loop.sh

# Metrics + prompt files only (open prompts manually in Cursor):
PMHC_OVERNIGHT_SKIP_AGENTS=1 bash scripts/run_overnight_loop.sh
```

## What one cycle does

| Step | Script | Purpose |
|------|--------|---------|
| 1 | `eval_package_benchmark.py` | Fixed 11-PDB recall@5 (package metric) |
| 2 | biology gate | Buried-anchor / anchor checks |
| 3 | `agent_controller.py` | Patch brief + agent orchestration |
| 4a | SDK / IDE parallel | **analyst** + **biology-reviewer** simultaneously (`Agent.create` × 2 or subagent delegation) |
| 4b | SDK sequential | **Patcher** → **Reviewer** (one subsystem) |
| 5 | `pytest` + re-eval | Package improved only if recall@5 ↑ and biology holds |

**No retrain by default.** Set `PMHC_OVERNIGHT_RETRAIN=1` to include `train_once.py`.

## Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `CURSOR_API_KEY` | — | Required for SDK agents |
| `PMHC_OVERNIGHT_MAX_CYCLES` | `1` | Cycles per run |
| `PMHC_OVERNIGHT_SKIP_AGENTS` | `0` | `1` = metrics/prompts only |
| `PMHC_OVERNIGHT_RETRAIN` | `0` | `1` = retrain before eval |
| `PMHC_OVERNIGHT_SAVE_BASELINE` | `1` | Snapshot eval baseline on cycle 1 |
| `PMHC_AGENT_MODEL` | `composer-2.5` | Cursor agent model |

## Manual agent mode (IDE)

Preferred: **`Use the overnight-orchestrator subagent`** (parallel analyst + biology-reviewer).

Without API key, open prompts (preamble included):

```text
artifacts/reports/agent_prompts/analyst_full.md
artifacts/reports/agent_prompts/biology_reviewer_full.md   # run in parallel with analyst
artifacts/reports/agent_prompts/patcher_full.md              # after both complete
artifacts/reports/agent_prompts/reviewer_full.md             # after patcher
```

Or invoke subagents by name: `analyst`, `biology-reviewer`, `patcher`, `reviewer`.

Then run validation:

```bash
python scripts/agent_controller.py --phase validate
```

## GitHub Actions

`overnight.yml` — workflow_dispatch; agents skipped unless `CURSOR_API_KEY` secret is set.

## Agent roles

See `.cursor/agents/` and `pmhc-hotspot-dev-plan.md`.

One-shot script (no agents): `bash scripts/run_cycle_once.sh`

STCRDab training manifest:

```bash
python scripts/stcrdab_to_manifest.py /path/to/stcrdab_summary.tsv
pmhc-hotspot ml-staged --manifest data/training_manifest.yaml --iedb data/iedb_mhc_ligand.csv --download
```

## Operational rhythm

1. **Train** — produces `artifacts/models/staged_xgb.joblib`
2. **Benchmark** — hybrid recall@5 + deterministic baseline
3. **Biology gate** — buried-anchor avoidance, anchor avoidance
4. **Metrics gate** — compare vs `baseline_metrics.json` and champion
5. **Promote** — copies passing model to `src/pmhc_hotspot/models/default_staged_xgb.joblib`
6. **Agent loop** — read `patch_brief.json`, patch one subsystem, review, re-run cycle

## Secrets (optional, for full nightly training)

- `PMHC_IEDB_URL` or `IEDB_EXPORT_URL` — direct download link to IEDB MHC ligand export

Without a secret, CI uses smoke mode (sample IEDB + mini manifest).

## Hard caps

- One accepted patch per cycle
- One model promotion per cycle
- No automatic PyPI release

## Biological validity

Biology gates run **before** promotion. A higher recall@5 never overrides buried-anchor violations.
