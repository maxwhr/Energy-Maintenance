# Task 28A R3B/R3C Formal Import Completion

## Status

`FORMAL_IMPORT_COMMITTED_RAG_COVERAGE_PARTIAL`

The controlled formal import was committed under the separately approved R3B
scope. The post-import data, review flow, idempotency, isolation, and
read-only reconciliation all pass. The full formal-import acceptance label is
not issued because the R3C browser retrieval coverage check returned a clean
source citation for 9 of 10 newly imported documents, not all 10.

## Controlled Import Evidence

- Frozen plan SHA-256: `00932bbb44ce7088fbd301e220a15f5ed02383c8b1b62aa23a5b7edef0fc7d8c`.
- Fresh pre-Apply backup: `.runtime/task28a-r3b/backups/energy_maintenance_preapply_retry_20260718_150154.dump`.
- Backup SHA-256: `2353bd58e043425c44b7a5de849850baba8bd5c49afbce941d88f9641da9fea7`.
- `pg_restore --list` passed for the backup.
- The formal import used the existing KnowledgeService, document parser,
  chunker, and review service. No direct SQL was used to insert documents or
  chunks.
- No migration, schema change, vector rebuild, external provider call, media
  import, Sungrow import, user case import, or test QA import was performed.

## Formal Database Reconciliation

| Item | Before | After | Result |
| --- | ---: | ---: | --- |
| `knowledge_documents` | 372 | 382 | +10, expected |
| `knowledge_chunks` | 4,791 | 5,728 | +937, expected |
| New Huawei SUN2000 documents | 0 | 10 | expected |
| New Huawei SUN2000 chunks | 0 | 937 | expected |
| Sungrow documents imported by R3B | 0 | 0 | isolated |

The ten document rows are all `manufacturer=huawei`,
`product_series=SUN2000`, `parse_status=parsed`, `review_status=approved`,
and `status=active`. Each has a service-created review record and the summed
chunk count is 937.

| Imported document | Document ID | Chunks |
| --- | --- | ---: |
| SUN2000 5KTL-12KTL M0 user manual | `27ed5237-9ace-4eba-8fa0-197447cea45a` | 59 |
| SUN2000-196KTL-H0++ user manual | `3e2c2964-eb25-4140-ba6e-c302c56131dd` | 93 |
| SUN2000 20KTL-M3 / 33KTL-NH / 40KTL-NH user manual | `dfd51875-99db-49e2-ac79-b4b27eb2e5ea` | 77 |
| SUN2000 App commissioning guide | `578d4c6b-1194-4b33-b305-4906a8c9ba1b` | 355 |
| SUN2000 5KTL-12KTL M1 user manual | `fed45934-7d1b-4633-9b1a-ecf5ae65b6dc` | 82 |
| SUN2000 15KTL / 17KTL / 20KTL M0 user manual | `fa5d3dd5-d80a-40d5-8162-04a6c8c9614c` | 62 |
| SUN2000 8KTL-20KTL M2 user manual | `20c72845-ed91-4c33-8a94-3e7648eb9df6` | 73 |
| Smart PV device replacement commissioning guide | `6021479b-d728-423c-8136-07d9181e3d43` | 19 |
| SUN2000 quick guide (Amphenol) | `b5424104-c986-482a-b297-9e251adbc7c9` | 9 |
| Inverter alarm reference | `516a3179-67d6-4b9a-bdcd-3c64e53cbb63` | 108 |

## Idempotency and Isolation

- The second identical Apply invocation imported `0` documents and `0`
  chunks, and skipped the same 10 documents as duplicates.
- The protected QA record digest remained unchanged.
- Non-target business baselines remained unchanged.
- The R3C post-browser read-only reconciliation reconfirmed all protected
  counts, `qa_records=2598`, `external_api_call_logs=676`, and
  `vector_index_runs=88` without deltas.

## Report-Path Gate Repair

The first committed Apply encountered its report output issue only after the
database transaction had completed because its report path was relative. The
immediate follow-up was an idempotent run using a valid absolute in-project
report path; it imported nothing and proved that no duplicate data was added.

R3C moves report-path validation before any database connection or write. The
guard now requires an absolute project-contained path, rejects literal `..`,
outside-prefix paths, and symbolic-link escapes, validates the parent directory
and writability, and verifies formal backup evidence before Apply. It also
checks plan/token/hash/acceptance/candidate scope before database access.

The repaired importer SHA-256 is
`bc96b40e8b12bff2ed575c64043415059b1b46cd126e214f638ce11b29592469`.
Because that differs from the frozen R3B importer hash, no future Apply may
reuse the historical plan without a newly frozen plan and explicit approval.

Targeted gate tests: `44 passed, 1 skipped`. The skipped case is the Windows
symbolic-link escape test because the current user lacks the privilege required
to create a test symbolic link; the guard itself remains implemented and other
path and gate tests pass.

## Remaining Acceptance Gate

The Amphenol quick guide is present, parsed, approved, active, source-traceable,
and visible in the browser. Its title, section, and all nine parsed chunk
excerpts did not return a citation to itself from the query-aware retrieval
route. This is a retrieval-coverage issue, not an import, parser, review, or
database-integrity failure. R3C did not alter retrieval ranking because that is
outside its authorized scope.
