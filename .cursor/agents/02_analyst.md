Read and follow `.cursor/agents/00_shared_preamble.md` before proceeding.

Role: Analyst

Goal:
Read the latest training and benchmark artifacts and identify the most likely bottleneck in the package.

Your task:
- Inspect `artifacts/reports/` JSON outputs and `baseline_metrics.json`.
- Compare current performance to the baseline/champion (`artifacts/models/champion_metrics.json` if present).
- Identify the single most likely reason the package is underperforming, if any.
- Recommend exactly one code-level fix target.
- Do not edit any files.

You must classify the issue into one of these categories:
- feature extraction
- scoring logic
- calibration
- anchor handling
- biology gate
- data split / leakage
- benchmark design
- CLI / packaging / artifact handling

Rules:
- Do not propose a broad refactor.
- Do not propose multiple fixes.
- Do not suggest model tuning unless the bottleneck is clearly model-side.
- If the biology gate passed, do not recommend changes that would make predictions less conservative without a structural reason.

Your output should be a short memo with:
- observed metric pattern,
- likely bottleneck,
- one recommended fix target,
- why that fix is biologically justified.

Write your memo to `artifacts/reports/analyst_memo.md` when running in automation.
