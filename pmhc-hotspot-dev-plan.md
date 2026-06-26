# pmhc-hotspot parallel agent dev plan

Five bounded Cursor agents improve the **package code** using shared artifacts. Training produces a new model bundle each cycle; agents patch code only when diagnostics justify it.

## Repository layout

```text
repo/
├── .github/workflows/
│   ├── train.yml
│   ├── benchmark.yml
│   └── agent-loop.yml
├── .cursor/agents/
│   ├── 00_shared_preamble.md
│   ├── 01_trainer.md
│   ├── 02_analyst.md
│   ├── 03_biology_reviewer.md
│   ├── 04_patcher.md
│   └── 05_reviewer.md
├── scripts/
│   ├── run_cycle_once.sh
│   ├── train_once.py
│   ├── benchmark_once.py
│   ├── biology_gate.py
│   ├── compare_metrics.py
│   ├── promote_champion.py
│   └── generate_patch_brief.py
├── artifacts/
│   ├── models/
│   └── reports/
├── baseline_metrics.json
└── src/pmhc_hotspot/
```

## Parallel execution model (package-first overnight)

```text
eval_package_benchmark (fixed 11 PDBs)
        │
        ▼
   biology gate
        │
   ┌────┴────┐
   ▼         ▼
 Analyst   Biology Reviewer   ← parallel (Cursor SDK or manual prompts)
   └────┬────┘
        ▼
     Patcher                    ← one subsystem only
        ▼
     Reviewer
        │ APPROVE
        ▼
  pytest + re-eval             ← package improved if recall@5 ↑
```

| Phase | Agents | Parallel? |
|-------|--------|-----------|
| 1 | Eval + biology gate | scripts only |
| 2 | Analyst + Biology Reviewer | **yes** |
| 3 | Patcher | after Analyst |
| 4 | Reviewer | after Patcher |
| 5 | pytest + re-eval | if APPROVE |

**Overnight entrypoint:** `bash scripts/run_overnight_loop.sh`

Legacy train-first loop:

Paste the shared preamble, then the role file, into separate agent sessions:

| Session | Prompt file |
|---------|-------------|
| 1 | `.cursor/agents/01_trainer.md` |
| 2 | `.cursor/agents/02_analyst.md` |
| 3 | `.cursor/agents/03_biology_reviewer.md` |
| 4 | `.cursor/agents/04_patcher.md` |
| 5 | `.cursor/agents/05_reviewer.md` |

Or run automation only (no agents):

```bash
bash scripts/run_cycle_once.sh
```

Then open Cursor only if `artifacts/reports/patch_brief.json` recommends a code change.

## Data buckets (no leakage)

| Bucket | What | Reused across runs? |
|--------|------|---------------------|
| **Training** | IEDB pretrain + structural rows from benchmark manifest (grouped CV) | Same files until you add **new** structures or labels |
| **Validation** | Grouped CV folds within training (by `pdb_id`) | Same split logic each run |
| **Evaluation** | Full benchmark manifest (TCR-contact recovery) | **Fixed** — compare runs, never fit on it |
| **Held-out** | `ml-holdout` PDB IDs | **Fixed** — never train on these |

### What this means

- **Each `train_once.py` run refits** the same staged stack (pretrain → statistical → finetune) on the **same training pool**. Weights change; data does not (until you add new PDBs or IEDB rows).
- **That is not leakage** as long as benchmark structures used for final recall@5 are evaluated only at inference, not used to tune code in a tight loop without holdout.
- **Genuine improvement** comes from (a) better package code, (b) new training structures, or (c) new IEDB — not from memorizing the benchmark.
- **Do not** tune patches until benchmark recall stops improving on the same 11 structures without checking `ml-holdout`.

## Models inside one bundle

One `staged_xgb.joblib` contains **three fitted models**, not three unrelated experiments:

1. Pretrain (XGBoost on IEDB) → `pretrain_prob`
2. Statistical (elastic-net on structure) → `stat_prob`
3. Finetune (XGBoost on structure + probs) → residue ranking

Each training cycle retrains this stack from scratch; architecture is fixed unless you change `PMHC_MODEL_TYPE`.

## Promotion rule

Promote only if:

1. Biology gate passes
2. Metrics gate passes (with AUC tolerance for CV noise)
3. Reviewer approved any code patch in this cycle (if applicable)

See `docs/AUTOMATION.md` for CI workflow details.
