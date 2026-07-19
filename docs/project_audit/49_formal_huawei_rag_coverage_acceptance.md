# Task 28A-R3D: Formal Huawei RAG Coverage Acceptance

## Latest R3G Authority

Task 28A-R3G reverified formal document coverage `10/10`, Amphenol
title/model/content coverage `3/3`, generic alarm scope isolation, and browser
citation traceability under the same production retrieval entry. Console and
authenticated API failure counts were zero. All database counts remained
unchanged. The latest overall status is `EARLY_RANKING_OPTIMIZATION_PARTIAL`,
because coverage passes but frozen post-import early-ranking thresholds do not.

## Execution Mode

Formal PostgreSQL was temporarily started by `pg_ctl` on port `55432` with
`default_transaction_read_only=on`. The Windows PostgreSQL service was not
started or reconfigured. All formal retrieval requests used preview mode
(`persist_result=false`) with local keyword retrieval only. No external
provider, OCR, LLM, embedding, vector rebuild, migration, import, reparse, or
knowledge-review transition was executed.

## Formal 10-document Coverage

`formal_10_document_rag_coverage.json` passed:

| Check | Result |
| --- | --- |
| Approved/active Huawei documents tested | 10 |
| Documents with at least one own real citation | 10 / 10 |
| Sungrow citations | 0 |
| Provider calls caused by R3D | 0 |
| Vector index runs caused by R3D | 0 |
| QA records added | 0 |
| Knowledge-document/chunk/QA count delta | 0 / 0 / 0 |

The Amphenol quick guide passed title, model, and chunk-content queries with
own citations at rank 1. The generic alarm query remained scoped to the real
inverter alarm reference document.

## Browser Source Trace

The real static frontend served by the temporary FastAPI instance on
`127.0.0.1:8012` was tested through headless Chrome CDP.

- the actual login form and `/knowledge/search` page rendered;
- a locally signed token for the existing administrator was used after a
  read-only user lookup, avoiding the normal `last_login_at` write;
- same-origin retrieval used `persist_result=false`, `enable_llm=false`, and
  `allow_real_api=false`;
- the actual search form rendered the target citation block for an Amphenol
  connector installation query;
- the returned citation traced through the real target document detail and a
  non-empty persisted chunk;
- console blocking errors: `0`; authenticated `/api` 4xx/5xx failures: `0`;
- no Sungrow citation was present.

Evidence: `.runtime/task28a-r3d/browser/browser_amphenol_trace.json`.

## Frozen 30-case Engineering Evaluation

The read-only frozen evaluation did **not** pass its full gate:

| Metric | Current | Task threshold | Result |
| --- | ---: | ---: | --- |
| Recall@1 | 0.392857 | 0.750000 | failed |
| Recall@3 | 0.714286 | 0.964286 | failed |
| Recall@5 | 0.821429 | 1.000000 | failed |
| MRR | 0.560714 | 0.854167 | failed |
| nDCG@5 | 0.626207 | 0.891228 | failed |
| Citation validity | 1.000000 | 1.000000 | passed |
| Citation support | 0.821429 | 1.000000 | failed |
| Manufacturer/product/model/alarm accuracy | 1.000000 | 1.000000 | passed |
| Safety and abstention | 1.000000 | 1.000000 | passed |
| Fabricated, cross-manufacturer, out-of-scope, pending/archived evidence | 0 | 0 | passed |

The evaluation has five failed cases. Failure analysis shows multiple cases
return current, valid, same-scope evidence while the frozen fixture requires a
specific historic chunk ID. That evidence-label alignment and the underlying
ranking recall must be reconciled in a separately authorized task; this task
did not weaken or edit the frozen 30-case dataset.

Current P50/P95 are `6305.524 ms` / `9166.616 ms`. No like-for-like R3D
pre-fix 30-case latency baseline exists, so a performance non-regression claim
is intentionally withheld.

Evidence: `.runtime/task28a-r3d/regression/task27a_30_final_current.json` and
`.runtime/task28a-r3d/diagnostics/regression_failure_evidence.json`.

## Final Reconciliation

| Table / evidence | Final count or state |
| --- | --- |
| knowledge_documents | 382 |
| knowledge_chunks | 5728 |
| qa_records | 2598 |
| diagnosis_records | 312 |
| maintenance_tasks | 138 |
| devices | 221 |
| uploaded_media | 414 |
| multimodal_maintenance_cases | 27 |
| knowledge_contributions | 126 |
| model_output_corrections | 15 |
| kg_nodes / kg_edges | 34 / 34 |
| sop_templates / sop_execution_records | 136 / 12 |
| users | 1463 |
| external_api_call_logs / vector_index_runs | 676 / 88, unchanged by R3D |

## Acceptance Status

`FORMAL_IMPORT_COMMITTED_RAG_COVERAGE_PARTIAL`

The formally imported Huawei documents are intact and 10/10 source coverage is
now achieved, including the Amphenol guide. Full formal Huawei RAG acceptance
is blocked solely by the frozen 30-case engineering quality gate, not by data
integrity, scope isolation, provider activity, QA persistence, or browser
source tracing.

## Task 28A-R3E Root-cause Addendum

The failure is now reproducibly isolated to corpus expansion rather than
current-code functional drift. Current code passes the unchanged 30-case v1
gate on the restored pre-import `372/4791` corpus and fails with the same five
R3D cases on the post-import `382/5728` corpus.

All five historical expected chunks remain active, approved, in scope, and
content-identical. New official Huawei material displaces them below Top 5 or
outside the surfaced candidate set, while current Top-5 evidence sets still
cover all required answer points. These sets are candidates pending expert
review, not approved equivalents. Therefore the authoritative status remains
`FORMAL_IMPORT_COMMITTED_RAG_COVERAGE_PARTIAL`; the next gate is
`EVIDENCE_EQUIVALENCE_REVIEW_REQUIRED`.

See `50_frozen_evaluation_comparability_audit.md` and
`51_frozen_evidence_equivalence_review.md`.

## Teardown

The temporary FastAPI process and the `pg_ctl` PostgreSQL instance were stopped
after verification. Ports `55432`, `55433`, and `8012` were confirmed
non-listening. The Windows service `postgresql-x64-16` remains `Stopped` and
`Disabled`.

R3E subsequently used a fresh task-started read-only 55432 process and an
isolated read-only 55434 comparison process. Both were stopped after the dual
evaluation; 55432, 55433, and 55434 were confirmed free, and the Windows
service remained `Stopped / Disabled`.

## Task 28A-R3F Acceptance Addendum

The expert review gate is now complete. An additive 30-case v2 preserves
frozen v1 and adds 12 expert-approved evidence sets for the five displaced
cases. On the formal post-import corpus, v2 reaches Recall@5 `1.000000`,
citation support `1.000000`, required-answer-point coverage `1.000000`, and
zero failed cases. Formal imported-document source coverage remains 10/10 and
the Amphenol categories remain 3/3.

Full acceptance is still blocked by early-ranking metrics: Recall@1
`0.464286`, Recall@3 `0.857143`, MRR `0.676786`, and nDCG@5 `0.758083` do not
meet the frozen gate. The status remains
`FORMAL_IMPORT_COMMITTED_RAG_COVERAGE_PARTIAL`; it must not be promoted to a
full formal Huawei RAG pass.
