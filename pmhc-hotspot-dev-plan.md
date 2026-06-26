# pmhc-hotspot — Binder-conditioning pipeline build spec

**Product framing:** pmhc-hotspot is a **binder-conditioning and validation platform**, not a standalone hotspot classifier. Hotspot prediction matters only insofar as it improves design-pipeline output versus reasonable controls.

**Central claim:** We improve binder design by conditioning RFdiffusion (and downstream ProteinMPNN / AF2) with better hotspot/patch priors — not “we predict TCR contacts perfectly.”

**Non-goals**

- Do not use docking scores as supervised labels.
- Do not treat the GNN/ML model as ground truth.
- Do not use RFdiffusion outputs as labels for the hotspot model.
- Do not stack correlated signals (docking + SASA + AF2) without ablations.

---

## Repo layout (target)

```text
hotspot-identification/
├── src/pmhc_hotspot/
│   ├── io/                 # structure I/O (existing io.py → migrate)
│   ├── preprocess/         # loaders, chain detection, example builder
│   ├── features/           # SASA, geometry, contacts (existing)
│   ├── labels/             # TCR-contact labels, split assignment
│   ├── models/             # ML bundles (existing)
│   ├── patches/            # patch detection + confidence (from scoring/patches)
│   ├── design/             # RFdiffusion / MPNN / AF2 handoff
│   ├── eval/               # downstream design validation metrics
│   ├── benchmark/          # contact-recovery benchmark (existing)
│   └── schema/             # canonical Pydantic contracts
├── configs/
│   ├── dataset.yaml
│   ├── features.yaml
│   ├── baseline.yaml
│   ├── design.yaml
│   └── eval.yaml
├── scripts/
│   └── run_pipeline.py     # orchestrator entry (Python)
├── data/
│   ├── raw/
│   └── processed/
├── artifacts/
│   ├── features/
│   ├── predictions/
│   ├── design_inputs/
│   ├── design_outputs/
│   ├── metrics/
│   └── reports/
├── experiments/
└── .cursor/
    ├── agents/             # ingest, feature, design, eval, gatekeeper, orchestrator
    └── skills/
```

**Orchestration language:** Python (`scripts/run_pipeline.py`). Bash wrappers optional for HPC only.

---

## Core data contracts

### 1. Canonical example (`schema/examples.py`)

One JSON-serializable object per complex. See `src/pmhc_hotspot/schema/examples.py`.

### 2. Design conditioning (`schema/conditioning.py`)

Hotspot/patch YAML consumed by design backends. See `docs/design-conditioning-format.md`.

### 3. Design eval report (`schema/design_eval.py`)

Downstream validation schema. See `docs/design-eval-schema.md`.

---

## Milestones

| ID | Name | Goal | Success criteria |
|----|------|------|------------------|
| **M1** | Deterministic baseline | Reproducible measurable pipeline | Same input → same output; serializable artifacts; single rebuild command |
| **M2** | Standard parser | Remove manual manifests for normal ops | PDB download + chain detect + frozen splits |
| **M3** | Docking prior | Geometry prior only, never labels | Ablations; docking score not a training target |
| **M4** | GNN prototype | Graph model vs XGBoost | Matches/beats baseline on held-out complexes |
| **M5** | Design-conditioning export | RFdiffusion-ready files + controls | One command; deterministic with seed |
| **M6** | Downstream validation | Prove design improvement | Predicted hotspots beat ≥1 control on primary metric |
| **M7** | Benchmark release | Frozen dataset + leaderboard | External users reproduce figures |

### Near-term build order (stop for human review after M1 + M5 skeleton)

1. Repo skeleton + schema + configs
2. Data loader + canonical example
3. Baseline features (existing) + patch export
4. Design-conditioning module + control generators
5. RFdiffusion job prep (not necessarily execution on day 1)
6. Eval schema + stub ranker
7. GNN + docking (later)

---

## Design experiment matrix

Per target, generate matched batches:

| Condition | Description |
|-----------|-------------|
| `random` | Random eligible peptide residues |
| `exposed_only` | Highest SASA residues |
| `central_only` | Central bulge positions (P3–P8) |
| `predicted` | pmhc-hotspot hotspots + patches |

Same `n_designs` per condition; same MPNN + AF2 ranking rules.

---

## Cursor agents (design feedback loop)

**Rule:** No agent both generates designs and judges them.

| Agent | Role | Edits code? |
|-------|------|-------------|
| **orchestrator** | Dispatch cycle; read manifest; call gatekeeper | No |
| **ingest** | Download/load structures; build examples | Yes (ingest only) |
| **feature** | Compute feature tables | Yes (features only) |
| **model** | Train baseline/GNN; write predictions | Yes (models only) |
| **design** | Export RFdiffusion inputs; fan out jobs | Yes (design/ only) |
| **eval** | MPNN + AF2 metrics; control comparison | Yes (eval/ only) |
| **gatekeeper** | APPROVE_PROMOTE / REJECT / RETRY | No |

### Cycle flow

```text
Planner (orchestrator) → hotspot/patch artifacts
    → design agent → RFdiffusion configs + job manifests
    → [HPC: RFdiffusion] → design_candidates/
    → eval agent → ranking_report.json
    → gatekeeper → promote | retry | stop
```

### Handoff artifacts (only structured files)

- `target.json`
- `hotspots.yaml` / `conditioning.yaml`
- `rfdiffusion_config.yaml`
- `design_candidates.csv`
- `ranking_report.json`
- `cycle_summary.md`

### Loop policy

- `max_cycles_per_target` (default 3)
- No promotion unless `predicted` beats ≥1 control on primary metric
- Stop if metrics unstable across repeat seeds

---

## CLI (target)

```bash
pmhc-hotspot build-dataset      # M2
pmhc-hotspot compute-features   # M1
pmhc-hotspot train-baseline     # M1 (existing ml-staged)
pmhc-hotspot export-designs     # M5
pmhc-hotspot run-design-validation  # M6
pmhc-hotspot release-benchmark  # M7
```

Existing commands (`run`, `benchmark`, `ml-staged`) remain until migrated.

---

## Validation gates (gatekeeper)

Promotion requires:

1. Parse success; no missing required schema fields
2. Baseline metrics stable vs prior release
3. Calibration / uncertainty within bounds
4. Design inputs generated for all control groups
5. Downstream: predicted condition beats ≥1 control
6. No leakage (eval PDBs not in training manifest)

---

## Legacy overnight loop

The package-patch overnight loop (analyst/patcher) lives on branch `overnight-automation` and is **separate** from this design-validation pipeline. Do not conflate the two.

---

## References

- `docs/design-conditioning-format.md` — hotspot/patch YAML
- `docs/design-eval-schema.md` — downstream metrics
- `configs/*.yaml` — run configuration
- `.cursor/agents/*.md` — agent prompts
