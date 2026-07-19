# Task 27A-R3 Checkpoint

## Completed

- Restored the R2 `NOT_READY` baseline without resetting existing work.
- Uniquely identified the production QA incident and created read-only inspection plus dry-run/authorized cleanup tooling.
- Confirmed cleanup is not authorized and was not executed.
- Confirmed no `_test` or `task27a` database exists, `energy_user` lacks `CREATEDB`, and no administrator URL is configured.
- Added a guarded test-database provisioner and administrator setup document.
- Ran safety script tests: 16 passed.
- Captured all nine failed cases through scope/hydration, keyword variants, fusion, guard, deterministic rerank, final Top 5, citations, and answer evidence.
- Verified frozen dataset hash and production QA count 2598 before/after diagnostics.
- Created the pre-change stage diagnostic report.
- Completed controlled phrase/proximity, intent-aware ranking, answer-window, ranking-calibration, and evaluator-normalization experiments.
- Rejected the broad phrase experiment after a model-ranking regression and retained only the scoped general rule.
- Re-ran the identical frozen 30-case set with the verified SHA-256.
- Passed all strict keyword engineering gates with zero failed cases and zero failure events.
- Added bounded evaluator normalization while retaining strict lexical scoring as the engineering-gate basis.
- Generated the 30-row expert review guide and sheet with every review decision left pending.
- Passed 84 targeted backend tests, compileall, frontend type checking, and a temporary Vite build.
- Passed a seven-case UTF-8 read-only API regression on temporary port 8014 with QA count 2598 before/after; the temporary instance was stopped.

## Final Findings

- All nine expected chunks are in the formal 621-chunk scope.
- The four former ranking failures now rank 1, 1, 1, and 2.
- All five former answer failures pass strict and normalized required-point coverage.
- Final strict metrics: R@1 0.75, R@3 0.964286, R@5 1.0, MRR 0.854167, nDCG@5 0.891228, citation support 1.0, answer coverage 1.0.
- Production counts remained 372 documents, 4791 chunks, and 2598 QA records throughout R3 read-only work.
- Persistence integration remains `BLOCKED_ADMIN_ACTION_REQUIRED`.

## Next Safe Step

An authorized PostgreSQL administrator must create `energy_maintenance_task27a_test` with owner `energy_user`. Only after the guarded database-name check should Alembic and the real persistence/Record Center acceptance run against that isolated database. Do not use or write the formal database for this acceptance. Human expert review and Hybrid evaluation remain separate later gates.
