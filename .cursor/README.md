# Cursor agents for pmhc-hotspot

Native Cursor **subagents** live in `.cursor/agents/` with YAML frontmatter (`name`, `description`).

## Subagents

| Subagent | File | When to use |
|----------|------|-------------|
| `overnight-orchestrator` | `overnight-orchestrator.md` | Start one full package-improvement cycle |
| `analyst` | `analyst.md` | Diagnose bottleneck (read-only) |
| `biology-reviewer` | `biology-reviewer.md` | Biology pass/fail (read-only) |
| `patcher` | `patcher.md` | One minimal code fix + test |
| `reviewer` | `reviewer.md` | APPROVE / REJECT patch |
| `trainer` | `trainer.md` | Retrain only when explicitly requested |

Shared rules: `agents/00_shared_preamble.md` (inlined into SDK prompts automatically).

## Parallel agents (IDE)

To run the overnight loop **inside Cursor** with true parallel subagents:

1. Say: **"Use the overnight-orchestrator subagent"**
2. Phase 2 launches **`analyst`** and **`biology-reviewer` in parallel** (one turn, two subagent delegations).
3. If patch needed: **`patcher`** → **`reviewer`** sequentially.

Or repeat cycles with the loop skill:

```
/loop 12h Use the overnight-orchestrator subagent for one package-improvement cycle
```

## Parallel agents (SDK / unattended)

For shell/CI overnight runs with `CURSOR_API_KEY`:

```bash
pip install -e ".[automation]"
export CURSOR_API_KEY=cursor_...

# Full cycle (metrics + parallel SDK agents + validate)
bash scripts/run_overnight_loop.sh

# Agents only (separate Agent.create per role, ThreadPoolExecutor)
python scripts/launch_parallel_agents.py --phase parallel
```

SDK uses `Agent.create()` per role (not `Agent.prompt()` one-shots) so analyst and biology-reviewer run concurrently.

## Metrics-only (no agents)

```bash
PMHC_OVERNIGHT_SKIP_AGENTS=1 bash scripts/run_overnight_loop.sh
```

See `docs/AUTOMATION.md` and `pmhc-hotspot-dev-plan.md` for data-split and biology rules.
