#!/usr/bin/env bash
# Run one full metrics cycle (no Cursor agents). Open agents only if patch_brief recommends a code change.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> fetch IEDB (if needed)"
"$PYTHON" scripts/fetch_iedb.py || PMHC_ALLOW_SMOKE_TRAIN=1 "$PYTHON" scripts/fetch_iedb.py

echo "==> train"
"$PYTHON" scripts/train_once.py

echo "==> benchmark"
"$PYTHON" scripts/benchmark_once.py

echo "==> biology gate"
"$PYTHON" scripts/biology_gate.py

echo "==> metrics gate"
"$PYTHON" scripts/compare_metrics.py || true

echo "==> promote (if gates pass)"
"$PYTHON" scripts/promote_champion.py || true

echo "==> patch brief"
"$PYTHON" scripts/generate_patch_brief.py

echo "==> done — inspect artifacts/reports/patch_brief.json"
