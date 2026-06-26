# Agent automation loop

Nightly GitHub Actions workflows train, benchmark, gate, and optionally promote a champion model.
Cursor agents use the reports to propose **one bounded package patch per cycle**.

## Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `train.yml` | nightly 02:00 UTC, manual | `scripts/train_once.py` → artifacts |
| `benchmark.yml` | after train succeeds, manual | benchmark + biology + metrics gates |
| `agent-loop.yml` | manual | `scripts/generate_patch_brief.py` for Cursor |

## Agent roles

| File | Role |
|------|------|
| `.cursor/trainer.md` | Train only; no code edits |
| `.cursor/analyst.md` | Diagnose bottleneck from reports |
| `.cursor/patcher.md` | One minimal code fix + test |
| `.cursor/reviewer.md` | Approve/reject; biology wins over metrics |

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
