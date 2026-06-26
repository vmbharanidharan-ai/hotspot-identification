# pmhc-hotspot agent orchestration

## Quick start (Cursor IDE)

```
Use the overnight-orchestrator subagent
```

The orchestrator runs eval metrics, then delegates to **analyst** and **biology-reviewer in parallel**, then patcher → reviewer if needed.

## Subagent registry

All subagents: `.cursor/agents/*.md` (YAML frontmatter required).

| `name` | Role |
|--------|------|
| `overnight-orchestrator` | Full cycle coordinator |
| `analyst` | Bottleneck diagnosis |
| `biology-reviewer` | Biology gate review |
| `patcher` | Minimal code patch |
| `reviewer` | Patch approval |
| `trainer` | Training only (optional) |

## Package-first loop

1. `eval_package_benchmark.py` — fixed 11-PDB eval manifest (no retrain)
2. Biology gate
3. **Parallel:** analyst + biology-reviewer
4. **Sequential:** patcher → reviewer (if needed)
5. `pytest` + re-eval → promote only if recall@5 improves and biology holds

Default: `PMHC_OVERNIGHT_RETRAIN=0`

## SDK parallel path

`src/pmhc_hotspot/automation/cursor_agents.py` — `launch_parallel()` with `ThreadPoolExecutor` + `Agent.create()` per role.
