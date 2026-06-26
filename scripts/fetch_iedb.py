#!/usr/bin/env python3
"""Fetch IEDB export for automated training."""

from __future__ import annotations

import os
import shutil
import sys
import urllib.request
from pathlib import Path

from pmhc_hotspot.automation.paths import DEFAULT_IEDB_PATH, SMOKE_IEDB_PATH


def main() -> int:
    target = DEFAULT_IEDB_PATH
    if target.exists() and target.stat().st_size > 0:
        print(f"IEDB already present: {target}")
        return 0

    url = os.environ.get("PMHC_IEDB_URL") or os.environ.get("IEDB_EXPORT_URL")
    if url:
        target.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading IEDB export from {url}")
        urllib.request.urlretrieve(url, target)
        print(f"Wrote {target}")
        return 0

    if os.environ.get("PMHC_ALLOW_SMOKE_TRAIN", "").lower() in {"1", "true", "yes"}:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SMOKE_IEDB_PATH, target)
        print(f"Smoke mode: copied {SMOKE_IEDB_PATH} -> {target}")
        return 0

    print(
        "IEDB export not found. Set PMHC_IEDB_URL / IEDB_EXPORT_URL, "
        "place data at data/iedb_mhc_ligand.csv, or set PMHC_ALLOW_SMOKE_TRAIN=1.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
