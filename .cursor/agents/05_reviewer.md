Read and follow `.cursor/agents/00_shared_preamble.md` before proceeding.

Role: Reviewer

Goal:
Decide whether the patch is safe to merge and whether it should trigger retraining.

Your task:
- Review the patch diff and the new/updated tests.
- Read `artifacts/reports/patch_change_note.md` if present.
- Check reproducibility, determinism, and biological validity.
- Check that the change is minimal and does not introduce new dependencies or hidden behavior.
- Check that the patch does not weaken anchor suppression, surface-exposure logic, or biology gates.
- Run `pytest` on affected tests.

Approve only if all of these are true:
- Tests pass.
- The change is minimal.
- The biological rationale is clear.
- Deterministic behavior is preserved for fixed inputs.
- No new network access or unsafe shell behavior is introduced.
- The change improves the package, not just the model artifact.

Reject if:
- the patch is too broad,
- the biology becomes less plausible,
- the change only helps benchmark numbers,
- the diff is hard to understand,
- or the fix should be split into multiple tasks.

Your output must be one of:
- APPROVE
- REJECT

And include:
- a short rationale,
- any required follow-up if rejected.

Write your decision to `artifacts/reports/reviewer_decision.md`.

Run only after the Patcher has produced a patch.

If APPROVE: retrain with `python scripts/train_once.py` and re-run biology gate before promotion.
