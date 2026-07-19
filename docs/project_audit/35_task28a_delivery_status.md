# Task 28A Delivery Status

## Latest Authoritative Status: Task 28A-R3G

`EARLY_RANKING_OPTIMIZATION_PARTIAL`

R3G retained only the safe Scope-snapshot cache and generic feature
precomputation. The authoritative four-cell functional metrics are unchanged
from R3F, while formal-v2 aggregate P95 improved from `6224.023 ms` to
`3074.891 ms`. Formal 10/10, Amphenol 3/3, browser citation tracing, zero-write
reconciliation, and frozen fixture hashes passed. The rejected A7 ranking
candidate improved the development set but failed its one-shot holdout and
four-cell regression, so it was rolled back. Full Huawei RAG acceptance is not
claimed because post-import v2 early-ranking metrics remain below threshold.

All older `Final Status` sections below are historical stage records. See
`57_formal_huawei_rag_final_acceptance.md` for the latest authority.

R3G final teardown stopped both task-started read-only PostgreSQL instances and
the temporary FastAPI process. Ports `55432/55433/55434/8013` are free and the
Windows PostgreSQL service remains `Stopped / Disabled`.

## Final Status

`TEST_DATABASE_ACCEPTANCE_PASSED_FORMAL_IMPORT_PREFLIGHT_READY_AWAITING_APPROVAL`

Task 28A-R2C completed the isolated PostgreSQL test-cluster acceptance path.
Task 28A-R3A-R1 subsequently completed a temporary, transaction-read-only
formal-database preflight. Controlled formal import remains deliberately closed:
it still requires a separate explicit approval, a fresh backup, and an
independent R3B Apply task.

## Completed

- PostgreSQL 16.14 binaries were discovered from the existing Windows service executable directory without starting or reconfiguring that service.
- A project-local PostgreSQL cluster was initialized at `.runtime/task28a/postgres/data` and bound only to `127.0.0.1:55433`.
- Start, stop, health, and restart behavior passed through fixed-path Task 28A scripts.
- `energy_maintenance_test_user` and `energy_maintenance_task27a_test` were provisioned with least privilege and verified ownership.
- Alembic migrated only the test database to `20260712_0015 (head)`.
- The real corpus importer processed 15 selected documents into 1,255 chunks with zero failures.
- Huawei 10 documents were approved; Sungrow 5 documents remained `pending_review` and were confirmed excluded from retrieval.
- All seven QA persistence checks and Record Center visibility checks passed.
- Both manual-confirmation fault cases passed with real citations, QA traces, diagnosis output, and SOP draft boundaries.
- External OCR, vision, cloud, local-model, vector, and formal-import calls remained at zero.
- Backend `compileall` and targeted retrieval/multimodal regression (`3 passed`) completed; frontend `vue-tsc --noEmit` completed.

## Intentionally Not Executed

- Any formal `energy_maintenance` write. R3A-R1 performed only a constrained
  read-only identity, schema, baseline, and duplicate-comparison preflight.
- Formal corpus import or Huawei production-scope change.
- Sungrow approval or inclusion in Huawei retrieval scope.
- OCR, MIMO, cloud-model, local-model, embedding, vector rebuild, or external API calls.

## Final Teardown

The project-local cluster was stopped after acceptance and port `55433` was confirmed non-listening. Temporary administrator and database environment variables were cleared. Project-local test data and logs remain only as audit evidence.

## Next Authorized Decision

Review the v2 plan and request a separate controlled formal-import task only
when an authorized expert provides the exact v2 approval token. No formal
import is implied by this preflight.

## Task 28A-R3A Formal Import Preflight

- Status: `BLOCKED_FORMAL_DATABASE_UNREACHABLE`
- Mode: dry-run only; no formal database write, migration, or Apply occurred.
- Frozen plan SHA-256: `5e803262a30276a78f21ba39f5a77553dc5099250b27d826c59b6771c5ba9f55`
- Required exact approval token: `not issued while preflight is blocked`
- A fresh `pg_dump -Fc` backup remains mandatory before any separately authorized Apply.

## Task 28A-R3A-R1 Formal Import Preflight Rerun

- Status: `PREFLIGHT_READY_AWAITING_APPROVAL`.
- Formal access was temporary and transaction-read-only; no formal business
  SQL write, migration, review, vector operation, backup, or importer Apply
  occurred.
- V1 blocked plan retained SHA-256:
  `5e803262a30276a78f21ba39f5a77553dc5099250b27d826c59b6771c5ba9f55`.
- V2 plan SHA-256:
  `200d21ed461ebd9c22d8adbb966b1504ff6ec8714efa4005ef6d0c772bfa0a20`.
- Candidate comparison: 10 Huawei `NEW_IMPORT_CANDIDATE`; conflict count `0`.
- Sungrow, media, and fault-case/user-case selected counts remain `0`.
- Before any separately authorized R3B Apply: revalidate the v2 hash and
  protected baseline, then create a fresh `pg_dump -Fc` backup.
- R3A-R1 teardown stopped its temporary formal instance and the test instance;
  `55432` and `55433` were both confirmed free while the Windows service stayed
  `Stopped` / `Disabled`.

## Task 28A-R3A-R2 Gate Contract Repair and v3 Preflight

- Status: `PREFLIGHT_V3_READY_AWAITING_APPROVAL`
- Mode: static gate validation plus formal/test PostgreSQL read-only preflight only.
- Formal database business writes, schema changes, backup creation, and Apply: `0`.
- Frozen v3 plan SHA-256: `00932bbb44ce7088fbd301e220a15f5ed02383c8b1b62aa23a5b7edef0fc7d8c`
- Required exact v3 approval token: `APPROVE_TASK28A_R3_FORMAL_IMPORT:00932bbb44ce7088fbd301e220a15f5ed02383c8b1b62aa23a5b7edef0fc7d8c`
- The v2 token is historical evidence only and is revoked for Apply.
- A fresh `pg_dump -Fc` backup remains required before any separately authorized Apply.

## Task 28A-R3B/R3C Controlled Formal Import and Closure Review

- R3B formally imported the separately approved v3 scope: `10` Huawei
  SUN2000 documents and `937` chunks. Formal knowledge counts changed from
  `372/4791` to `382/5728` as expected.
- All imported documents are parsed, approved, active, source-traceable, and
  have review records. The second identical Apply was idempotent: `0` new
  documents and `0` chunks; `10` duplicates skipped.
- Sungrow import remains `0`; protected QA and non-target business baselines
  remain unchanged; no vector rebuild or external provider call was performed.
- R3C repaired the importer report-path gate before database connection and
  verified relevant static tests (`44 passed, 1 skipped` for unavailable
  Windows symlink creation privilege).
- R3C read-only browser verification passed for list visibility, document
  detail, chunk content, and source tracing. Query-aware retrieval reached
  `9/10` imported documents with real self-citations. The approved Amphenol
  quick guide did not return its own citation after title, section, and parsed
  content-excerpt queries.
- Current status: `FORMAL_IMPORT_COMMITTED_RAG_COVERAGE_PARTIAL`. Do not claim
  `FORMAL_HUAWEI_IMPORT_ACCEPTANCE_PASSED` until that single retrieval coverage
  issue is resolved and re-verified without re-importing formal data.

## Task 28A-R3D Retrieval Coverage Repair

- The approved Huawei SUN2000 Amphenol quick guide retrieval defect was traced
  to citation validation, not candidate recall or data integrity. Its PDF
  chunks have reliable page locators but no recovered heading path.
- A generic citation rule now accepts non-empty, approved, active PDF chunks
  with a real page locator and the real parent document title when no section
  locator is available. Scope, manufacturer, status, review, and content gates
  remain mandatory; no target-specific branch was added.
- Formal read-only coverage is now `10/10`; the Amphenol document has own
  citations for title, model, and chunk-content queries, each with best rank 1.
- Browser source trace passed using same-origin preview retrieval with no QA
  persistence, provider call, vector operation, document mutation, or import.
- The frozen 30-case Huawei engineering evaluation remains `NOT_READY`
  (Recall@1 `0.392857`, Recall@3 `0.714286`, Recall@5 `0.821429`, MRR
  `0.560714`, nDCG@5 `0.626207`). Consequently the current authoritative
  status remains `FORMAL_IMPORT_COMMITTED_RAG_COVERAGE_PARTIAL`, not full
  formal acceptance.

## Task 28A-R3E Comparability And Evidence Review

- The pre-import backup was restored to an isolated, read-only PostgreSQL
  cluster on `127.0.0.1:55434`; baseline `372/4791/2598` and Alembic
  `20260712_0015` were verified.
- Current code exactly reproduced the historical frozen functional metrics on
  the pre-import corpus, including zero failures.
- The same code and fixed parameters reproduced the R3D post-import result on
  the formal read-only corpus: five failures and Recall@5 `0.821429`.
- Root cause classification is
  `CORPUS_EXPANSION_RANKING_COMPETITION_CONFIRMED`; the five expected chunks
  still exist unchanged but are below Top 5 or no longer in the surfaced/raw
  candidate set.
- All five current official evidence sets are
  `CANDIDATE_REQUIRES_EXPERT_REVIEW`; none was automatically approved and
  frozen v1 was not modified.
- Delivery status remains `FORMAL_IMPORT_COMMITTED_RAG_COVERAGE_PARTIAL` with
  `EVIDENCE_EQUIVALENCE_REVIEW_REQUIRED` as the next decision gate.

## Task 28A-R3F Expert Review and v2 Evaluation

- The completed 24-row expert CSV was validated under SHA-256
  `a0867811660c6630088cf9a15cb83e344201ab1528041bf442216b34390b7354`.
  Reviewer `张三` and review date `2026-07-06` are real supplied review data.
- All five cases were classified `EQUIVALENT_EVIDENCE_APPROVED`; no case was
  classified as ranking-repair-required or unresolved.
- Frozen v1 remains byte-identical. Additive v2 contains all 30 cases and 12
  accepted evidence sets, with SHA-256
  `f9a000f45fd12571adebea90b52b97cf4cf5fe9dba01a8c33f80de5b2db68d68`.
- Post-import v2 restores Recall@5 and citation support to `1.000000` with zero
  failed cases, but Recall@1 `0.464286`, Recall@3 `0.857143`, MRR `0.676786`,
  and nDCG@5 `0.758083` remain below the frozen early-ranking gate.
- The authoritative delivery status therefore remains
  `FORMAL_IMPORT_COMMITTED_RAG_COVERAGE_PARTIAL`; expert review is complete,
  but generic early-ranking remediation is still required.

## Task 28A-R3H Score-contract and Ranking Acceptance

- Score-provenance loss and non-monotonic rerank were confirmed and repaired;
  variant-vote multiplication and requested-information overmatch were not
  confirmed as causal root causes.
- Independent R3H Dev passed with R@1/3/5
  `0.866667/0.952381/0.980952`, but the one-shot Holdout reached only
  `0.800000/0.840000/0.880000`, with scope isolation `0.700000`.
- Frozen pre-import v1/v2 and post-import v2 acceptance gates also failed.
  Performance, formal 10/10, Amphenol 3/3, safety/scope regression, browser,
  leakage, and zero-write checks passed.
- Authoritative status is now `RANKING_OVERFIT_DETECTED`. Full formal Huawei
  RAG acceptance must not be claimed.

## Task 28A-R3I Product Acceptance Attempt

- Status: `TASK28A_R3I_BLOCKED_BY_PREEXISTING_UNRESOLVED_MERGE`.
- The task-start working tree already contained `MERGE_HEAD` and eight
  unresolved paths, including Provider, knowledge, retrieval, and Task 29B
  login/auth sources. Task boundaries prohibited resolving those conflicts.
- Backend compile, targeted tests, frontend build, new backend startup, the
  isolated workflow, and current-source formal API/browser acceptance were
  therefore blocked. No trial retrieval rollback was retained.
- Formal read-only identity, Alembic, all protected counts, 10 Huawei documents,
  937 imported chunks, and zero Sungrow import contamination passed.
- Residue inventory is ready for user review; formal writes/deletes remain 0.
- Delivery must not be marked passed until the merge is explicitly resolved
  and R3I is rerun.
