# Task 28A-R3F Post-expansion Ranking and Dual-gate Acceptance

## Latest R3G Authority

`EARLY_RANKING_OPTIMIZATION_PARTIAL`

R3G retained a safe performance optimization only. The four-cell functional
matrix below remains unchanged, formal-v2 P95 improved to `3074.891 ms`, and
all coverage/integrity/browser checks passed. A7's development improvement did
not generalize to the one-shot holdout and regressed the four-cell matrix, so
its ranking behavior was rejected. See reports 55-57 for the full diagnosis,
ablation record, and final acceptance boundary.

## Controlled Evaluation Matrix

All four cells used keyword retrieval only, `top_k=5`, three warmups, three
complete 30-case runs, concurrency 1, `persist_result=false`,
`enable_llm=false`, and `allow_real_api=false`.

| Corpus / dataset | R@1 | R@3 | R@5 | MRR | nDCG@5 | Citation support | Failed cases |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A pre-import / v1 | 0.750000 | 0.964286 | 1.000000 | 0.854167 | 0.891228 | 1.000000 | 0 |
| B pre-import / v2 | 0.785714 | 0.964286 | 1.000000 | 0.877976 | 0.909086 | 1.000000 | 0 |
| C post-import / v1 | 0.392857 | 0.714286 | 0.821429 | 0.560714 | 0.626207 | 0.821429 | 5 |
| D post-import / v2 | 0.464286 | 0.857143 | 1.000000 | 0.676786 | 0.758083 | 1.000000 | 0 |

V2 restores Top-5 evidence coverage, citation support, required-answer-point
coverage, and all five previously failed cases. It does not meet the frozen
post-expansion early-ranking thresholds for Recall@1, Recall@3, MRR, or
nDCG@5. The final status therefore remains
`FORMAL_IMPORT_COMMITTED_RAG_COVERAGE_PARTIAL`.

## Reviewed-case Final Ranks

| Case | Preferred accepted evidence rank |
| --- | --- |
| HUAWEI-MODEL-002 | 1 |
| HUAWEI-INSULATION-004 | 4 |
| HUAWEI-COMM-002 | 4 |
| HUAWEI-TEMP-001 | combined set ranks 2 and 4 |
| HUAWEI-GRID-003 | 5 |

These ranks explain the result: evidence is complete within Top 5, but several
preferred sources are not early enough to satisfy the frozen early-ranking
gate. No label relaxation or case-specific production ranking override was
used.

## Coverage, Browser, and Performance

- Formal imported-document own-citation coverage: 10/10 passed.
- Amphenol quick-guide title/model/content coverage: 3/3 passed.
- Authenticated browser acceptance: five reviewed cases passed, source and
  page tracing rendered, no console errors, no authenticated API failures.
- Post-import v1 aggregate latency: P50 `2880.747 ms`, P95 `6388.382 ms`.
- Post-import v2 aggregate latency: P50 `3811.825 ms`, P95 `6224.023 ms`.
- P95 change: `-2.5728%`; no greater-than-15% P95 regression.

## Data Protection

Formal counts remained exactly 382 documents, 5,728 chunks, and 2,598 QA
records. All protected business counts also matched the pre-run baseline.
Task-created QA records, provider calls, vector runs, corpus writes, schema
changes, and Alembic changes were all zero. Huawei scope remained isolated and
no Sungrow citation contamination was observed.

## Acceptance Decision

Expert-review ingestion and dataset v2 creation: passed. Formal 10-document
coverage and browser source tracing: passed. Full frozen post-expansion ranking
gate: failed. A later task may perform generic ranking remediation against a
separate development corpus, but must retain v1/v2, frozen thresholds, source
truth, and formal read-only protection.
