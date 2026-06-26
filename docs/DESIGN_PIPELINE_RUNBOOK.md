# Binder-conditioning pipeline runbook

How to run **Phase 1 ingest** and the **Cursor agent** workflow for the pmhc-hotspot design platform.

---

## Do I need an API key?

| How you run it | API key? |
|----------------|----------|
| **Phase 1 ingest only** (`build-dataset`, `run_pipeline.py ingest`) | **No** |
| **Cursor IDE** — chat with orchestrator / ingest subagents | **No** (uses your logged-in Cursor session) |
| **Cursor CLI** — `agent login` then `agent chat` | **No** (browser auth) |
| **Headless SDK** — `scripts/launch_design_cycle.py` | **Yes** — `CURSOR_API_KEY` from [cursor.com/dashboard](https://cursor.com/dashboard) → Integrations / API keys |

You only need an API key if you want agents to run **outside** the IDE (cron, Longleaf, GitHub Actions, overnight loops).

---

## One-time setup

```bash
cd ~/Projects/hotspot-identification   # or your clone path
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,schema]"
```

Optional for SDK automation:

```bash
pip install cursor-sdk
export CURSOR_API_KEY="key_..."   # from Cursor dashboard
```

---

## Phase 1 — Ingest (implemented)

Builds `ComplexExample` JSON under `data/processed/examples/{split}/`.

### Option A — CLI

```bash
# Holdout 11 PDBs from benchmark manifest (downloads to data/pdb/)
pmhc-hotspot build-dataset --config configs/dataset.yaml

# Offline / custom STCRDab training set
pmhc-hotspot build-dataset \
  --config configs/dataset.yaml \
  --stcrdab /path/to/STCRDab_summary.tsv \
  --download
```

Flags:

- `--no-download` — only use PDBs already in `data/pdb/`
- `--processed-dir PATH` — override output directory
- `--stcrdab PATH` — add STCRDab rows (excludes eval PDBs by default)

### Option B — Pipeline script

```bash
python scripts/run_pipeline.py ingest
python scripts/run_pipeline.py design-export
```

### M5 — Design export (four control groups)

```bash
pmhc-hotspot export-design --config configs/design.yaml
```

Writes `artifacts/design_inputs/{target_id}/{random,exposed_only,central_only,predicted}.yaml`.

### Feature enrichment

```bash
pmhc-hotspot compute-features --config configs/features.yaml
```

Populates `residue_features` on each `ComplexExample` JSON (in-place by default).

### M6 — Design validation (stub mode)

```bash
pmhc-hotspot run-design-validation --config configs/eval.yaml
```

Writes `artifacts/metrics/{target_id}/ranking_report.json` and gatekeeper verdict.
Uses proxy metrics until AF2/MPNN outputs exist (`ranking.af2_multimer: true` in config).

### Full pipeline

```bash
python scripts/run_pipeline.py all
```

Runs: ingest → features → design-export → design-eval (+ gatekeeper).

### Outputs

| Path | Description |
|------|-------------|
| `data/processed/examples/holdout/*.json` | 11 eval complexes |
| `data/processed/examples/train/*.json` | STCRDab training examples (when TSV provided) |
| `data/processed/dataset_manifest.json` | Build summary |
| `data/processed/ingest_report.json` | Skips, provenance, STCRDab stats |

### Config

Edit `configs/dataset.yaml`:

- `sources`: `pdb_manifest` (eval set) and/or `stcrdab`
- `stcrdab.path`: set to your STCRDab summary TSV on Longleaf/Mac
- `download`: `true` to fetch missing PDBs from RCSB

---

## Cursor agents (IDE — no API key)

Agent definitions live in `.cursor/agents/`:

| Agent | Role |
|-------|------|
| `orchestrator` | Dispatches phases, does not edit science code |
| `ingest` | Phase 1 data layer |
| `feature` | Residue feature tables |
| `design` | Export RFdiffusion conditioning YAML (four control groups) |
| `eval` | Design validation report |
| `gatekeeper` | APPROVE_PROMOTE / REJECT / RETRY |

### Run one cycle in chat

Open the repo in Cursor, then in Agent chat:

> Use the **orchestrator** subagent to run one binder-conditioning cycle: ingest → features → design-export. Start with ingest if `data/processed/examples/` is empty.

Or target a single phase:

> Use the **ingest** subagent to verify Phase 1 ingest and fix any failing tests in `tests/test_preprocess.py`.

The orchestrator reads `pmhc-hotspot-dev-plan.md` and `configs/*.yaml`.

### Shell entry (manifest only for non-ingest phases)

```bash
python scripts/run_pipeline.py design-export   # writes artifacts/reports/pipeline_run_manifest.json
```

---

## Cursor agents (SDK — API key required)

For unattended / HPC runs:

```bash
export CURSOR_API_KEY="key_..."
pip install cursor-sdk

# One phase
python scripts/launch_design_cycle.py ingest

# Full sequence: ingest → features → design-export → design-eval → gatekeeper
python scripts/launch_design_cycle.py --all

# Preview prompts without calling the API
python scripts/launch_design_cycle.py ingest --dry-run
```

Implementation: `src/pmhc_hotspot/automation/cursor_agents.py`

**Note:** SDK agents edit code in your working tree (local runtime). Commit or branch before long runs.

---

## Verify ingest

```bash
pytest tests/test_preprocess.py tests/test_schema.py -q
```

Smoke build on the synthetic structure (no network):

```bash
pytest tests/test_preprocess.py::test_build_dataset_offline -q
```

---

## Longleaf notes

```bash
module load python/3.11   # adjust for your cluster
cd /work/users/v/m/vmbharan/RNAseq/GSE114922_MDS_Pel/hotspot-identification
source .venv/bin/activate
pmhc-hotspot build-dataset --config configs/dataset.yaml \
  --stcrdab /path/to/STCRDab_summary.tsv
```

For overnight SDK loops, use `screen`/`tmux` and `launch_design_cycle.py`; ingest itself is pure Python and does not need the SDK.

---

## What’s next (M3–M7)

- **M3** — docking geometry prior (`docking_prior` flag in features config; never a label)
- **M4** — GNN prototype vs XGBoost baseline
- **M6 live** — wire ProteinMPNN / AF2 outputs (set `ranking.af2_multimer: true` in eval config)
- **M7** — frozen benchmark release + leaderboard

See `pmhc-hotspot-dev-plan.md` for the full milestone table.
