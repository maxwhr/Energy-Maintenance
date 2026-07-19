# Task 28A-R3I Product Functional Acceptance

> Historical Blocked Attempt: this report preserves the first R3I run that
> stopped at the pre-existing unresolved merge. It is retained as audit
> evidence and is not the result of the authorized M1/R1 rerun.

## Status

`TASK28A_R3I_BLOCKED_BY_PREEXISTING_UNRESOLVED_MERGE`

Task 28A-R3I did not reach product functional acceptance. The task started
while a Git merge was already in progress (`MERGE_HEAD` present) with eight
unmerged paths. Four conflicted backend files contain literal merge markers:

- `backend/app/api/routes/retrieval.py`
- `backend/app/services/knowledge_service.py`
- `backend/app/services/model_adapters/cloud_openai_adapter.py`
- `backend/app/services/retrieval_service.py`

The same merge also leaves conflicts in the frontend retrieval API and the
three Task 29B login/auth source files. Resolving those conflicts would require
choosing between merge sides and modifying Provider, knowledge-service, and
login/auth files that Task 28A-R3I explicitly forbids. No merge, reset,
restore, checkout, commit, or push was executed.

## Authorization And Task 29B

- The explicit Task 28A-R3I approval token was present and validated.
- Test-database writes were authorized only for
  `energy_maintenance_task28a_r3i_test`.
- Formal access was transaction-read-only; formal delete was disabled.
- The existing Task 29B process remained on PID `40372`, port `8000`, and
  returned the Energy-Maintenance health/OpenAPI identity.
- `/login` and `/auth/login` returned the new Task 29B pages in a real browser.
- Both pages loaded without warning/error console entries. No login form was
  submitted, so no formal `last_login_at` write was attempted.
- Static login bundle SHA-256 remained
  `a58b964019161ec34aa2e1c536c99197c3f381b3cd07845cd02fea2a7524bba9`.

## Retrieval Safety Decision

The pre-task production path still contains the R3H candidate behavior and its
historical status remains `RANKING_OVERFIT_DETECTED`. A trial restoration of
the previously verified R3G safe path was not retained because the unresolved
source merge prevented compilation, regression evaluation, isolated-database
verification, and a new backend startup. All seven authorized retrieval files
were returned to their exact task-start SHA-256 values.

The intended R3G product-safe candidate remains:

`A1_scope_snapshot_plus_A2_precomputed_features_safe_rollback`

Its historical evidence remains valid, but it was not reactivated by this
task. The consumed R3G/R3H Holdout data was not rerun or used for tuning.

## Verification Results

- Backend `compileall`: failed on the four pre-existing backend merge markers.
- Targeted R3G/R3H unit tests: failed during collection on the Provider merge
  marker; no test case executed.
- Frontend build: failed on pre-existing merge markers in retrieval/login
  sources.
- New backend instances `8031` and `8032`: not started.
- Isolated test-database knowledge/auth workflow: not executed.
- Frozen four-cell evaluation: not executed.
- Formal retrieval/API/browser functional acceptance: not executed against
  current source.
- Production hardcoding and frozen-fixture leakage scan: passed (327 runtime
  Python files; zero literal/fixture-path findings).
- Frozen v1/v2 hashes remained unchanged.

## Formal Read-only Evidence

The formal PostgreSQL instance was started on `127.0.0.1:55432` with
`default_transaction_read_only=on`. Identity, Alembic `20260712_0015`, and all
17 protected table counts matched the required baseline. The ten Task 28A
Huawei documents remain parsed, approved, active, Huawei/SUN2000 scoped, and
contain 937 chunks. Sungrow contamination in the imported set is zero.

No formal row was inserted, updated, deleted, reviewed, reparsed, archived, or
persisted. Provider, embedding, vector rebuild, and external API calls were
zero.

## Decision

Product functional acceptance is blocked by the pre-existing unresolved merge,
not by a newly observed formal-data defect. The merge must be resolved in a
separately authorized task, followed by a fresh Task 28A-R3I run from the
documented task-start hashes. Until then, neither
`TASK28A_PRODUCT_FUNCTIONAL_ACCEPTANCE_PASSED` nor
`FORMAL_HUAWEI_RAG_FUNCTIONAL_ACCEPTANCE_PASSED` may be claimed.
