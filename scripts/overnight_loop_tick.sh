#!/usr/bin/env bash
# One overnight cycle tick — called by 12h loop or manually.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PMHC_OVERNIGHT_MAX_CYCLES=1
export PMHC_OVERNIGHT_SKIP_AGENTS=1
export PMHC_OVERNIGHT_RETRAIN="${PMHC_OVERNIGHT_RETRAIN:-0}"
# Use hybrid when model bundle present
if [ -f "src/pmhc_hotspot/models/default_staged_xgb.joblib" ] || [ -f "artifacts/models/staged_xgb.joblib" ]; then
  export PMHC_EVAL_SCORING_MODE="${PMHC_EVAL_SCORING_MODE:-hybrid}"
fi
python3 scripts/agent_controller.py --phase all
code=$?
echo "overnight_tick_exit=$code"
exit "$code"
