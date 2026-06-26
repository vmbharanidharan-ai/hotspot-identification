# Cursor agent prompts

Use the five-role parallel layout in **`agents/`**:

| File | Role |
|------|------|
| `agents/00_shared_preamble.md` | Shared rules (paste at top of every session) |
| `agents/01_trainer.md` | Train once, write artifacts |
| `agents/02_analyst.md` | Diagnose bottleneck |
| `agents/03_biology_reviewer.md` | Biology pass/fail |
| `agents/04_patcher.md` | One minimal code fix |
| `agents/05_reviewer.md` | APPROVE / REJECT |

See **`pmhc-hotspot-dev-plan.md`** for orchestration and data-split rules.

Legacy single-file prompts (`trainer.md`, `analyst.md`, etc.) are deprecated; use `agents/` instead.
