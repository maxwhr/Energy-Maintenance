# Task 28A-R3I-M1 Pre-existing Merge Resolution And Baseline Archive

## Status

`PREEXISTING_MERGE_RESOLVED_AND_VALIDATED_FOR_LOCAL_ARCHIVE`

This report records the selective resolution of the merge that already
existed before Task 28A-R3I-M1 began. No pull, fetch, new merge, rebase,
cherry-pick, reset, restore, checkout, clean, stash, database write, external
provider call, or push was performed.

## Git Evidence

- Current branch: `main`
- Local development HEAD: `d56f9b157fafde5ca95ad8892c9094cdd14a4608`
- Incoming MERGE_HEAD: `b2d32a7bc45eea5133da4770ee49708b27dc22c9`
- ORIG_HEAD: `d56f9b157fafde5ca95ad8892c9094cdd14a4608`
- Merge base: `53145339c66b6efed489156ea68cf55d24161ab8`
- Merge message: `Merge branch 'main' of https://github.com/maxwhr/Energy-Maintenance`
- Safety branch: `backup/r3i-pre-merge-20260719`
- Safety branch target: `d56f9b157fafde5ca95ad8892c9094cdd14a4608`
- Initial merge-index paths reviewed: 173
- Initial unmerged paths: 8
- Full three-way evidence: `.runtime/task28a-r3i-merge/conflicts/`
- Full decision inventory: `.runtime/task28a-r3i-merge/merge_scope/full_merge_change_inventory.json`

The incoming commit was the tracked remote-side merge commit. The current
local HEAD contained the newer locally accepted Task 29B authentication UI,
RAG safety work, knowledge review behavior, and provider controls.

## Resolution Inventory

All 173 paths already present in the merge index were reviewed before the
index was changed.

| Decision | Count | Result |
| --- | ---: | --- |
| `ACCEPT_INCOMING` | 10 | Accepted low-risk frontend presentation changes after build and browser checks. |
| `MANUAL_MERGE` | 8 | Compared Stage 1, Stage 2, Stage 3, and working content hunk by hunk. |
| `REJECT_INCOMING` | 155 | Rejected older, duplicated, unsafe, unapproved, or out-of-scope changes. |

The accepted frontend source files were `DataPanel.vue`, `EmptyState.vue`,
`PageFrame.vue`, the new `PageNotice.vue`, `layout/index.vue`, `global.css`,
`device/Alarms.vue`, `device/Models.vue`, `diagnosis/index.vue`, and
`error/403.vue`. Their API values and business enums were not changed.

The rejected incoming set included default vector-search enablement,
unapproved lexical-vector and bulk-vectorization paths, an auto-approval
sample importer, provider paths that did not preserve the current
`allow_real_api` boundary, a frontend chat path that forced cloud execution,
duplicate sample media, and reports that overstated cloud/vector acceptance.

The installed files under `backend/static/frontend` were rebuilt locally
from the reviewed frontend source. They are generated output, not an
acceptance of the incoming static bundle.

## Conflict Decisions

For each conflict, Stage 2 was proven byte-equivalent to the task-start local
HEAD and was retained only after comparing it with the base and incoming
version. No bulk ours/theirs command was used.

| Path | Resolution |
| --- | --- |
| `backend/app/api/routes/retrieval.py` | Kept authenticated/RBAC-aware route, preview and persistence controls, scope filters, citations, traces, and query-aware service call. |
| `backend/app/services/knowledge_service.py` | Kept parser/chunker/review flow, pending/archive isolation, source trace, operation log, scope cache invalidation, and no automatic approval. |
| `backend/app/services/model_adapters/cloud_openai_adapter.py` | Kept environment-only secrets, disabled-by-default real calls, timeout and sanitized error behavior. |
| `backend/app/services/retrieval_service.py` | Kept current citation, scope, abstention, persistence, cache/snapshot, R3G, and task-start R3H semantics for Phase B ablation. |
| `frontend/src/api/retrieval.ts` | Kept the current `/api` contract and safe defaults for persistence, provider, scope, and citations. |
| `frontend/src/views/Login.vue` | Kept the Task 29B public landing page and five approved photovoltaic-maintenance visual assets. |
| `frontend/src/views/AuthLogin.vue` | Kept the Task 29B token/user-store login flow, safe redirect, loading, and error handling. |
| `frontend/src/views/Register.vue` | Kept administrator-managed account guidance with no public registration write path. |

## Protected Baselines

- Database models changed: no
- Alembic files changed: no
- Database connected during Phase A: no
- Formal database writes: 0
- External provider calls: 0
- Embedding/vector calls: 0
- Frozen v1 SHA-256: `9d2400a26f2a50ea3894b46ee2d5e2f88392ee1a539695a9467490e6d9ff20b0`
- Frozen v2 SHA-256: `f9a000f45fd12571adebea90b52b97cf4cf5fe9dba01a8c33f80de5b2db68d68`
- Reviewer identity preserved: `张三`
- The production `17A` technical chunk was not inspected as residue or changed.

## Validation

- Source merge markers: 0
- Unmerged index entries: 0
- `git diff --check`: passed
- Backend compileall (`app scripts`): passed
- Targeted backend suite: 134 passed, 1 skipped
- Consumed R3G/R3H Holdout rerun: no
- Frontend TypeScript check: passed through `npm run build`
- Frontend production build: passed
- Static frontend installation: passed
- `npm audit`: 0 vulnerabilities
- `/login`, `/auth/login`, `/register`: HTTP 200
- Five Task 29B image assets: HTTP 200
- Desktop/mobile horizontal overflow: none
- Browser console errors: 0
- Static API failures in the no-login browser smoke: 0
- Staged secret scan: passed before archive commit

The PowerShell profile emitted the host's existing execution-policy warning
in some command logs. It did not change command results. The static installer
also printed an unrelated Conda activation warning before completing with a
successful exit code.

## Archive Boundary

The local merge archive commit is created only after the final staged diff,
secret scan, frozen-fixture hashes, conflict count, compile, tests, build, and
browser checks pass. It must have both original parents and must not be
pushed. Phase B may begin only from that clean local merge baseline.
