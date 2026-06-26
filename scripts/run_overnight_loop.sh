#!/usr/bin/env bash
# Overnight package-improvement loop (package code first, optional retrain).
#
# Requirements for automated Cursor agents:
#   export CURSOR_API_KEY=...
#   pip install -e ".[dev,ml,automation]"
#
# Manual mode (no API key): runs eval + writes agent prompts to
#   artifacts/reports/agent_prompts/*_full.md
#
set -euo pipefail

PYTHON="${PYTHON:-python3}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MAX_CYCLES="${PMHC_OVERNIGHT_MAX_CYCLES:-1}"
SAVE_BASELINE="${PMHC_OVERNIGHT_SAVE_BASELINE:-1}"
RETRAIN="${PMHC_OVERNIGHT_RETRAIN:-0}"
SKIP_AGENTS="${PMHC_OVERNIGHT_SKIP_AGENTS:-0}"

echo "==> pmhc-hotspot overnight package loop"
echo "    cycles=$MAX_CYCLES retrain=$RETRAIN save_baseline=$SAVE_BASELINE"

for cycle in $(seq 1 "$MAX_CYCLES"); do
  echo ""
  echo "========== Cycle $cycle / $MAX_CYCLES =========="
  export PMHC_OVERNIGHT_CYCLE="$cycle"

  args=(--phase all --cycle "$cycle")
  if [ "$SAVE_BASELINE" = "1" ] && [ "$cycle" -eq 1 ]; then
    args+=(--save-baseline)
  fi
  if [ "$RETRAIN" = "1" ]; then
    args+=(--retrain)
  fi
  if [ "$SKIP_AGENTS" = "1" ]; then
    args+=(--skip-agents)
  fi

  set +e
  "$PYTHON" scripts/agent_controller.py "${args[@]}"
  code=$?
  set -e

  if [ "$code" -eq 0 ]; then
    echo "Cycle $cycle: package improved or acceptable."
  elif [ "$code" -eq 2 ]; then
    echo "Cycle $cycle: no package improvement detected (eval recall flat/down)."
  else
    echo "Cycle $cycle: failed (exit $code)."
    exit "$code"
  fi

  # Only snapshot baseline after first successful cycle if not already saved
  SAVE_BASELINE=0
done

echo ""
echo "==> Done. Inspect:"
echo "    artifacts/reports/eval_benchmark_report.json"
echo "    artifacts/reports/eval_compare.json"
echo "    artifacts/reports/overnight_state.json"
echo "    In Cursor IDE (parallel subagents): use overnight-orchestrator subagent"
echo "    artifacts/reports/agent_outputs/ (SDK agent mode)"
