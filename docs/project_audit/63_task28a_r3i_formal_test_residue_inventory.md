# Task 28A-R3I Formal Test Residue Inventory

> Historical Blocked Attempt: this read-only inventory belongs to the first
> R3I run. It remains evidence for comparison and does not authorize cleanup
> or replace the revalidated inventory required by R1.

## Status

`RESIDUE_CLASSIFICATION_REQUIRES_USER_REVIEW`

The formal database was scanned only in transaction-read-only mode. Discovery
keywords were used to locate candidates and were never treated as delete
conditions.

## Baseline And Scope

- Database: `energy_maintenance` on `127.0.0.1:55432`.
- Read-only settings: transaction and default transaction both `on`.
- Alembic: `20260712_0015`.
- All required protected-table counts matched the Task 28A-R3I baseline.
- Formal writes: `0`; formal deletes: `0`.

The read-only scan covered QA, diagnosis, maintenance tasks, uploaded media,
multimodal cases, corrections, knowledge contributions, SOP templates and
executions, operation logs, and external API call logs.

## Candidate Classification

The broad scan found 3,138 keyword candidates. A separate exact `17-A / 17A /
17 A` search added one unique business-content candidate, for 3,139 audited
candidates in total:

- `CONFIRMED_TEST_RESIDUE`: 1
- `LIKELY_TEST_REQUIRES_REVIEW`: 434
- `PRODUCTION_OR_AUDIT_RETAIN`: 15
- `UNKNOWN_NO_ACTION`: 2,689

Most candidates only contain normal technical IDs or cite nested demo/test
evidence. They are not safe deletion candidates. Likely candidates retain
no-action status until exact origin and dependency review is approved.

## Known QA Incident

The exact QA row `4a9eeab8-91de-43bb-90ec-78a3d6bba7be` exists with trace
`qa_req_a92bd4d743373941ff949e900b972057` and the known request marker. The
query is `SUN2000-100KTL-M1 通信参数`; it has zero citations. Existing Task 27A
incident reports explicitly identify it as an integration-test write, so it is
the sole `CONFIRMED_TEST_RESIDUE` candidate.

The row was not modified or deleted. A future cleanup still requires a fresh
`pg_dump -Fc`, `pg_restore --list`, exact plan-hash approval, and before/after
API/UI/count verification.

## “17-A” Result

The only exact business-content match is knowledge chunk
`b31b7107-9306-4286-b9c3-a9036212b5ac`, document
`20c72845-ed91-4c33-8a94-3e7648eb9df6`, chunk index 61, page 81, section
`10 技术数据`.

It is the rated maximum output-current value `17A` in the approved, active,
parsed Huawei manual `SUN2000-(8KTL-20KTL)-M2 用户手册`. The parent document
has 73 active chunks, one approval review record, and one knowledge-review
operation log. This is formal technical knowledge, not a test label. Its
classification is `PRODUCTION_OR_AUDIT_RETAIN`; proposed action is `retain`.

## Artifacts

- Raw discovery:
  `.runtime/task28a-r3i/residue_inventory/formal_candidate_discovery.json`
- Classified inventory:
  `.runtime/task28a-r3i/residue_inventory/formal_residue_classification.json`
- Dependency graph:
  `.runtime/task28a-r3i/residue_dependencies/formal_residue_dependency_graph.json`
- Dry-run cleanup plan:
  `docs/project_audit/task28a_formal_test_residue_cleanup_plan.json`
- Plan SHA-256:
  `c9cd9cfa850046d4e3610380289fa6213561c98a4093eb8bf6883b794ac320a8`

The future approval token is recorded in the task summary artifact. It was not
used. The plan remains `DRY_RUN_READY_AWAITING_EXPLICIT_APPROVAL` and performs
no deletion.

## Limitations

The unresolved source merge prevented Record Center/API browser correlation
and full API dependency checks. The generated dependency graph therefore marks
likely candidates as no-action and requires a fresh exact-ID dependency audit
before any future cleanup.
