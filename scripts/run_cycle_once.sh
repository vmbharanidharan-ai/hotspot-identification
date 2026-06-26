#!/usr/bin/env bash
# Run one full metrics cycle (no Cursor agents). Open agents only if patch_brief recommends a code change.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> fetch IEDB (if needed)"
python scripts/fetch_iedb.py || PMHC_ALLOW_SMOKE_TRAIN=1 python scripts/fetch_iedb.py

echo "==> train"
python scripts/train_once.py

echo "==> benchmark"
python scripts/benchmark_once.py

echo "==> biology gate"
python scripts/biology_gate.py

echo "==> metrics gate"
python scripts/compare_metrics.py || true

echo "==> promote (if gates pass)"
python scripts/promote_champion.py || true

echo "==> patch brief"
python scripts/generate_patch_brief.py

echo "==> done — inspect artifacts/reports/patch_brief.json"
