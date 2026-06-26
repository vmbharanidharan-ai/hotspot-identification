Read and follow `.cursor/agents/00_shared_preamble.md` before proceeding.

Role: Trainer

Goal:
Train the current model stack once, save the model artifact, and write a clean training report.

Your task:
- Run `python scripts/train_once.py` exactly once (after `python scripts/fetch_iedb.py` if needed).
- Use the fixed repository data and manifest.
- Save the resulting bundle to `artifacts/models/`.
- Save metrics and fold summaries to `artifacts/reports/`.
- Do not edit source code.
- Do not edit tests.
- Do not edit data files.
- Do not attempt any code fixes.

Required outputs:
- `artifacts/models/staged_xgb.joblib`
- `artifacts/reports/training_report.json`
- `artifacts/reports/fold_metrics.json`
- `artifacts/reports/failure_slices.json` if any failure pattern is visible

What to include in the report:
- ROC-AUC or other primary score.
- Recall@5 or similar hotspot metric (from benchmark if already run; otherwise note pending).
- Biology-gate relevant observations.
- Any clear failure modes by allele, peptide length, or structural class.
- Whether the model appears stable or noisy across folds.

If training fails:
- Write a short failure summary to `artifacts/reports/training_failure.json`.
- Stop immediately.
- Do not guess at a fix.

Important:
Your job is only to produce training artifacts and diagnostic notes.
