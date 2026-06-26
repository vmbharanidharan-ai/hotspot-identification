#!/usr/bin/env bash
# Repeat overnight orchestrator cycles until a wall-clock deadline (default: 12h from start).
#
# Wakes the Cursor agent every INTERVAL seconds with AGENT_LOOP_TICK_pmhc_overnight.
# Each tick: full orchestrator cycle + commit-gate agent decides whether to commit.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DURATION_SEC="${PMHC_OVERNIGHT_DURATION_SEC:-43200}"   # 12 hours
INTERVAL_SEC="${PMHC_OVERNIGHT_INTERVAL_SEC:-1800}"  # 30 minutes between cycles
START_TS="$(date +%s)"
DEADLINE_TS="$((START_TS + DURATION_SEC))"
DEADLINE_ISO="$(date -u -r "$DEADLINE_TS" '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u -d "@$DEADLINE_TS" '+%Y-%m-%dT%H:%M:%SZ')"

mkdir -p artifacts/reports
python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
payload = {
    "started_at": datetime.now(timezone.utc).isoformat(),
    "deadline_unix": $DEADLINE_TS,
    "deadline_utc": "$DEADLINE_ISO",
    "interval_sec": $INTERVAL_SEC,
    "duration_sec": $DURATION_SEC,
}
Path("artifacts/reports/overnight_deadline.json").write_text(json.dumps(payload, indent=2))
print(json.dumps(payload, indent=2))
PY

PROMPT='Run pmhc-hotspot overnight-orchestrator cycle in '"$ROOT"'. Deadline UTC: '"$DEADLINE_ISO"'. (1) python3 scripts/agent_controller.py --phase metrics. (2) Launch analyst and biology-reviewer subagents IN PARALLEL in one turn. (3) If biology PASS and patch needed: patcher then reviewer sequentially. (4) python3 scripts/agent_controller.py --phase validate. (5) Launch commit-gate subagent to write artifacts/reports/commit_gate_decision.md. (6) python3 scripts/apply_commit_gate.py. Stop this cycle if past deadline. Use hybrid if src/pmhc_hotspot/models/default_staged_xgb.joblib exists.'

echo "==> Overnight repeat loop until $DEADLINE_ISO (every ${INTERVAL_SEC}s)"
echo "    First cycle runs immediately via agent; subsequent ticks every $((INTERVAL_SEC / 60)) min"

# Emit first wake immediately (cycle 0)
echo "AGENT_LOOP_TICK_pmhc_overnight $(python3 -c "import json; print(json.dumps({'prompt': '''$PROMPT''', 'cycle': 0, 'deadline_unix': $DEADLINE_TS}))")"

while true; do
  now="$(date +%s)"
  if [ "$now" -ge "$DEADLINE_TS" ]; then
    echo "AGENT_LOOP_DONE_pmhc_overnight {\"reason\":\"deadline_reached\",\"deadline\":\"$DEADLINE_ISO\"}"
    break
  fi
  sleep "$INTERVAL_SEC"
  now="$(date +%s)"
  if [ "$now" -ge "$DEADLINE_TS" ]; then
    echo "AGENT_LOOP_DONE_pmhc_overnight {\"reason\":\"deadline_reached\",\"deadline\":\"$DEADLINE_ISO\"}"
    break
  fi
  cycle=$(( (now - START_TS) / INTERVAL_SEC + 1 ))
  echo "AGENT_LOOP_TICK_pmhc_overnight $(python3 -c "import json; print(json.dumps({'prompt': '''$PROMPT''', 'cycle': $cycle, 'deadline_unix': $DEADLINE_TS}))")"
done
