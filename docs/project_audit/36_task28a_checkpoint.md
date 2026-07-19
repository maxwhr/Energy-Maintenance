# Task 28A Checkpoint

## Latest Checkpoint: Task 28A-R3G

- Status: `EARLY_RANKING_OPTIMIZATION_PARTIAL`.
- Final candidate: A1 Scope snapshot plus A2 feature precomputation; A3-A7
  ranking behavior rejected and rolled back.
- Four-cell functional metrics and v1/v2 hashes: unchanged.
- Formal-v2 P50/P95: `2178.977/3074.891 ms`.
- Formal 10/10, Amphenol 3/3, browser trace, compileall, and 54 focused tests:
  passed.
- Formal and pre-import protected-table/Scope deltas: zero; both write probes
  rejected; no provider or vector call added.
- Remaining stage: a new independent ranking study is required; the consumed
  R3G holdout cannot be reused for tuning.

The checkpoints below are retained as historical evidence.

## File Inventory

- Status: `COMPLETED`
- Allowed source root: preserved in the Task 28A source inventory report
- Allowed project root: `D:\Work Space\Energy-Maintenance`
- Files migrated: `167`
- SHA-256 verified: `167`
- Manifest documents: `21`
- Fault images: `144`

## Remaining Stages

| Stage | Status |
| --- | --- |
| Safe migration | completed: 167 moved and hash verified |
| Knowledge import manifest | completed: 21 documents, 144 media assets, 2 metadata exclusions |
| Project-local test cluster / test role/database | completed on `127.0.0.1:55433`; cluster stopped after acceptance |
| Alembic on test database | passed: `20260712_0015 (head)` |
| Test knowledge import | passed: 15 parsed documents and 1,255 chunks |
| Huawei review / Sungrow isolation | passed: Huawei 10 approved; Sungrow 5 pending and excluded |
| QA persistence / Record Center | passed: seven checks plus list/detail/trace/timeline |
| Fault image runtime cases | passed: two manual-confirmation cases; external calls 0 |
| Controlled formal import | v2 preflight ready; Apply not executed |
| Final regression | passed: compileall, targeted pytest 3 passed, frontend typecheck |

## Historical Checkpoints

Task 28A-R2A correctly found no project-stored administrator credential, and Task 28A-R2B correctly stopped when `Get-Command` could not locate PostgreSQL commands. Task 28A-R2C was subsequently authorized to inspect service metadata and discovered a complete PostgreSQL 16.14 binary set through the existing Windows service `PathName`. See `40_postgres_admin_credential_discovery.md`, `41_project_local_postgres_test_cluster.md`, and `42_postgresql_binary_discovery_and_resume.md`.

## Current Boundary

The Task 28A test-database objective is complete. R3A-R1 also completed the
formal read-only comparison. The next pending decision is whether an authorized
expert will open a separately reviewed R3B Apply using the exact v2 token. This
checkpoint does not authorize an import.

## Task 28A-R3A Formal Import Preflight

- Status: `BLOCKED_FORMAL_DATABASE_UNREACHABLE`
- Mode: dry-run only; no formal database write, migration, or Apply occurred.
- Frozen plan SHA-256: `5e803262a30276a78f21ba39f5a77553dc5099250b27d826c59b6771c5ba9f55`
- Required exact approval token: `not issued while preflight is blocked`
- A fresh `pg_dump -Fc` backup remains mandatory before any separately authorized Apply.

## Task 28A-R3A-R1 Checkpoint

- Formal database read-only preflight: passed on `127.0.0.1:55432`.
- Formal Alembic revision: `20260712_0015`; SQLAlchemy model tables missing:
  `0`.
- Read-only write-protection probe: rejected by PostgreSQL and rolled back.
- Protected QA record digest: unchanged across two read-only reads.
- Candidate comparison: 10 Huawei candidates / 937 chunks; all 10 are
  `NEW_IMPORT_CANDIDATE`, with zero conflicts and zero invalid candidates.
- V2 plan SHA-256:
  `200d21ed461ebd9c22d8adbb966b1504ff6ec8714efa4005ef6d0c772bfa0a20`.
- Approval state: `PREFLIGHT_READY_AWAITING_APPROVAL`; no R3B Apply occurred.
- Final runtime state: the temporary formal and test PostgreSQL instances were
  stopped; ports `55432` and `55433` were released; the Windows service remains
  `Stopped` / `Disabled` without configuration changes.

## Task 28A-R3A-R2 Gate Contract Repair and v3 Preflight

- Status: `PREFLIGHT_V3_READY_AWAITING_APPROVAL`
- Mode: static gate validation plus formal/test PostgreSQL read-only preflight only.
- Formal database business writes, schema changes, backup creation, and Apply: `0`.
- Frozen v3 plan SHA-256: `00932bbb44ce7088fbd301e220a15f5ed02383c8b1b62aa23a5b7edef0fc7d8c`
- Required exact v3 approval token: `APPROVE_TASK28A_R3_FORMAL_IMPORT:00932bbb44ce7088fbd301e220a15f5ed02383c8b1b62aa23a5b7edef0fc7d8c`
- The v2 token is historical evidence only and is revoked for Apply.
- A fresh `pg_dump -Fc` backup remains required before any separately authorized Apply.

## Task 28A-R3B/R3C Checkpoint

- Controlled formal Apply: committed under the approved v3 scope, with `10`
  Huawei SUN2000 documents and `937` chunks.
- Formal database counts: documents `372 -> 382`; chunks `4791 -> 5728`.
- Import review state: all ten parsed, approved, active, and traceable; second
  Apply idempotency passed with zero new rows and ten duplicate skips.
- R3C post-browser formal read-only reconciliation passed: protected QA,
  non-target counts, provider-call log count, and vector-index-run count have
  no delta.
- Browser knowledge list/source/chunk acceptance passed. Query-aware targeted
  RAG is `9/10`; the `SUN2000 quick guide (Amphenol)` is visible and healthy
  but has no own citation under the tested controlled retrieval queries.
- Current checkpoint: `FORMAL_IMPORT_COMMITTED_RAG_COVERAGE_PARTIAL`.

## Task 28A-R3I Checkpoint

- Checkpoint: `TASK28A_R3I_BLOCKED_BY_PREEXISTING_UNRESOLVED_MERGE`.
- Task 29B static `/login` and `/auth/login` remain available with zero browser
  warning/error entries, but the current source has eight unresolved merge
  paths and cannot be built or started as a fresh instance.
- Formal read-only counts remain exactly `382/5728/2598` for documents,
  chunks, and QA; Alembic remains `20260712_0015`; task formal writes/deletes
  are 0.
- One confirmed QA test residue and 434 likely candidates require future exact
  review. The `17A` match is a real page-81 current rating in an approved Huawei
  manual and must be retained.
- Frozen v1/v2 hashes remain unchanged. No Provider, embedding, vector, schema,
  Alembic, or consumed-Holdout operation occurred.

## Task 28A-R3H Checkpoint

- Frozen candidate: `B7_frozen_candidate_r4`; production aggregate SHA-256
  `8ba17a3d0ee82e4e57479099146c4460758815ebd58dd30e65182dae22818965`.
- New Dev: 115 cases, passed its gate. New Holdout: 60 cases, run exactly
  once, failed R@3/R@5, citation support, scope isolation, and failed-case
  gates. No post-Holdout tuning occurred.
- Post-import v2 finished at R@1/3/5
  `0.571429/0.785714/0.928571`, MRR `0.688690`, nDCG@5 `0.747884`, and two
  failed cases. The performance ceiling passed at P95 `3054.218 ms`.
- Formal database deltas, QA additions, provider calls, vector runs, schema,
  Alembic, and frozen fixture hashes remained unchanged.
- Checkpoint: `RANKING_OVERFIT_DETECTED`.

## Task 28A-R3F Checkpoint

- Expert review validation: passed for 24/24 rows and all five affected cases.
- Frozen v1 hash remains
  `9d2400a26f2a50ea3894b46ee2d5e2f88392ee1a539695a9467490e6d9ff20b0`.
- Additive expert-reviewed v2 hash is
  `f9a000f45fd12571adebea90b52b97cf4cf5fe9dba01a8c33f80de5b2db68d68`.
- Four-cell, three-run evaluation completed. Post-import v2 achieved R@1/3/5
  `0.464286/0.857143/1.000000`, MRR `0.676786`, nDCG@5 `0.758083`, citation
  support `1.000000`, and failed cases `0`.
- Formal 10/10 coverage, Amphenol 3/3 coverage, and authenticated browser
  source tracing passed. Formal database writes, QA additions, provider calls,
  vector runs, schema changes, and Alembic changes were zero.
- Checkpoint remains `FORMAL_IMPORT_COMMITTED_RAG_COVERAGE_PARTIAL` because the
  frozen early-ranking thresholds are not yet met.

## Task 28A-R3E Checkpoint

- Fixture SHA-256 remains
  `9d2400a26f2a50ea3894b46ee2d5e2f88392ee1a539695a9467490e6d9ff20b0`.
- PREIMPORT_CURRENT_CODE: Recall@1/3/5
  `0.750000/0.964286/1.000000`, MRR `0.854167`, nDCG@5 `0.891228`, failures
  `0`.
- POSTIMPORT_CURRENT_CODE: Recall@1/3/5
  `0.392857/0.714286/0.821429`, MRR `0.560714`, nDCG@5 `0.626207`, failures
  `5`.
- Three-run aggregate P50/P95: pre-import `3120.881/4371.010 ms`;
  post-import `6634.581/10066.550 ms`.
- Eligible scope grew from 621 to 1,558 chunks; repeated full-scope hydration
  and per-variant local scoring are the performance root-cause candidates.
- Formal document/chunk/QA, provider-log, and vector-run deltas are all zero.
- Expert review material contains 24 candidate rows with all human decision
  fields blank. No v2 and no ranking change were created.
  Retrieval coverage repair is required before formal acceptance can be marked
  passed. No re-import, document mutation, or migration is authorized.

## Task 28A-R3D Checkpoint

- Formal data integrity and source isolation: passed in transaction-read-only
  mode. The target Amphenol quick guide remains parsed, approved, active,
  Huawei/SUN2000 scoped, reviewed, and has nine non-empty active chunks.
- Citation coverage repair: passed. The generic PDF page-plus-parent-title
  traceability rule restored target citations without hard-coded document IDs,
  manufacturer exceptions, data changes, or candidate/ranking overrides.
- Formal imported-document own-citation coverage: `10/10` passed. Target
  title/model/chunk categories: `3/3`, best own rank `1` for each.
- Browser source tracing: passed, with a rendered real citation block and no
  authenticated API errors under same-origin `persist_result=false` retrieval.
- Frozen 30-case Huawei keyword gate: failed. It remains the only R3D blocker
  to `FORMAL_HUAWEI_IMPORT_ACCEPTANCE_PASSED`; do not re-import or mutate the
  formal corpus as a workaround.
- Current checkpoint: `FORMAL_IMPORT_COMMITTED_RAG_COVERAGE_PARTIAL`.
