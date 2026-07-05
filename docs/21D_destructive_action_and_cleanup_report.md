# Task 21D Destructive Action And Cleanup Report

## Scope

Task 21D covered development-test-data cleanup, destructive action acceptance, permission blocking, and port/database environment review.

This task did not generate or update any delivery package and did not perform Git staging or commit.

## No-package Confirmation

- delivery zip: not generated
- `delivery/`: not modified
- `delivery_staging/`: not created
- `Compress-Archive`: not executed
- migration upgrade: not executed
- new migration: not created

## No-git Confirmation

- `git add`: not executed
- `git commit`: not executed
- current changes remain unstaged

## Environment

- Energy-Maintenance backend URL used for tests: `http://127.0.0.1:8010`
- `GET http://127.0.0.1:8010/api/health`: passed, returned `Energy-Maintenance`
- `http://127.0.0.1:8000/api/health`: not Energy-Maintenance in this environment
- `8000`: occupied by other listeners
- `8010`: Energy-Maintenance backend listener
- `5432`: occupied by Docker / WSL relay listeners
- `55432`: native PostgreSQL listener
- PostgreSQL Windows service `postgresql-x64-16`: `Stopped / Disabled`
- PostgreSQL runtime used by backend: standalone native `postgres.exe` on `55432`

## Task21C Cleanup

Cleanup script enhanced:

- Added `Task21C_` and `Task21D_` marker recognition.
- Added `users` table scanning.
- Added safe soft-clean handling for Task-marked users and devices.
- Added `--only-pattern` to avoid broad cleanup of older acceptance traces.

Executed cleanup:

```powershell
cd "D:\Work Space\Energy-Maintenance\backend"
uv run python scripts\cleanup_dev_test_data.py --only-pattern Task21C_
uv run python scripts\cleanup_dev_test_data.py --only-pattern Task21C_ --execute --confirm CLEAN_DEV_TEST_DATA
uv run python scripts\cleanup_dev_test_data.py --only-pattern Task21C_
```

Result:

- Task21C dry-run before cleanup: 11 matched rows.
- Task21C execute: 11 rows soft-archived / disabled / retired.
- Task21C dry-run after cleanup: 0 matched rows.
- Uploaded files were not removed.
- Audit traces and QA/diagnosis-style immutable records were retained.

## Task21D Destructive Action Results

Script:

```text
backend/scripts/check_task21d_destructive_actions.py
```

Machine-readable result:

```text
.runtime/task21d/destructive_actions_result.json
```

Marker:

```text
Task21D_20260630223342
```

Created Task21D temporary data:

- users: 5
- devices: 1
- knowledge_documents: 3
- knowledge_contributions: 1
- sop_templates: 1
- maintenance_tasks: 1
- corrections: 1
- kg_candidates rejected: 1

Results:

- user disable / enable: passed
  - admin disabled a Task21D user.
  - disabled login was rejected.
  - admin enabled the user.
  - enabled login succeeded.
  - viewer disable attempt was blocked.
- device retire: passed
  - engineer created and retired a Task21D device.
  - retired device detail showed `retired`.
  - viewer retire attempt was blocked.
- knowledge archive: passed
  - Task21D document retrieved after approval.
  - viewer archive attempt was blocked.
  - expert archive succeeded.
  - archived document no longer participated in retrieval.
- knowledge reject: passed
  - engineer/viewer reject attempts were blocked.
  - expert reject succeeded.
  - rejected document did not participate in retrieval.
- contribution reject / archive: passed
  - engineer created and submitted contribution.
  - expert rejected it.
  - owner engineer could view/edit rejected contribution.
  - viewer archive attempt was blocked.
  - expert archive succeeded.
- SOP template archive: passed
  - created active Task21D template matched SOP generation.
  - viewer archive attempt was blocked.
  - expert archive succeeded.
  - archived template no longer matched generation.
- task cancel: passed
  - admin created and assigned Task21D task.
  - viewer cancel attempt was blocked.
  - unrelated engineer start attempt was blocked.
  - admin cancelled task.
  - cancelled task could not be started or completed.
- correction resolve: passed
  - engineer created correction from a real QA trace.
  - viewer resolve attempt was blocked.
  - expert accepted correction.
- KG candidate reject: passed
  - Task21D document extraction produced a candidate.
  - viewer candidate reject attempt was blocked.
  - expert reject succeeded.

## Browser Destructive Clicks

- executed: no
- passed: not applicable
- skipped: yes
- notes:
  - Destructive browser clicks were intentionally not executed against list-row selectors because exact-ID API workflow is safer and prevents accidental action on formal demo data.
  - Task 21C already covered real browser page rendering and main non-destructive form/button interactions.
  - Task 21D destructive behavior was verified through exact backend API calls against Task21D-prefixed temporary data only.

## Verification

- `uv run python -m compileall app scripts`: passed
- `uv run python -m alembic -c alembic.ini current`: passed, `20260601_0003 (head)`
- `npm.cmd run build`: passed
- `powershell -ExecutionPolicy Bypass -File .\scripts\final_smoke_test.ps1 -BaseUrl http://127.0.0.1:8010`: passed, `failed = 0`
- `uv run python scripts\check_task21d_destructive_actions.py --base-url http://127.0.0.1:8010`: passed

Note: final smoke emitted a Conda PowerShell profile encoding error before the script output, but the Energy-Maintenance smoke checks themselves completed with `status = passed` and `failed = 0`.

## Retained Audit Traces

The cleanup script intentionally does not hard-delete uploaded files or immutable audit-style traces.

Retained examples:

- knowledge review records
- QA records
- diagnosis records
- model call logs
- operation logs
- uploaded files on disk

## Remaining Problems

### P0

- None found in this task.

### P1

- Browser destructive row-click testing remains skipped for safety; exact-ID API destructive workflow passed.

### P2

- Task21D final temporary records remain in the database as acceptance evidence and can be soft-cleaned later with:

```powershell
cd "D:\Work Space\Energy-Maintenance\backend"
uv run python scripts\cleanup_dev_test_data.py --only-pattern Task21D_ --execute --confirm CLEAN_DEV_TEST_DATA
```

### External Blocked

- PostgreSQL Windows service is still `Stopped / Disabled`; current validation uses standalone `postgres.exe`.
- `8000` and `5432` remain occupied by other local listeners.
- Cloud model, local llama.cpp, and OCR real external acceptance remain outside Task 21D.

## Final Judgment

- destructive actions: passed
- cleanup: passed for Task21C, final Task21D records retained as evidence
- permissions: passed
- package generation: not executed
- Git commit: not executed
- ready for next testing: yes

