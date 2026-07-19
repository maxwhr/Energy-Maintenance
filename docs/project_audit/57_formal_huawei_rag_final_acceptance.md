# Task 28A Formal Huawei RAG Final Acceptance

## R3I Authoritative Product Addendum

`FORMAL_HUAWEI_RAG_FUNCTIONAL_ACCEPTANCE_PASSED`

The restored R3G safe baseline reproduces the expert-v2 product gate with
Recall@5, citation validity/support, required-point coverage, safety, Scope,
and abstention all `1.000000`, failed cases `0`, P50 `1763.571 ms`, and P95
`2485.602 ms`. Formal document coverage is `10/10`, Amphenol coverage is
`3/3`, and formal database writes are `0`.

Recall@1/3, MRR, and nDCG remain diagnostic only. Early ranking is deferred as
`ENGINEERING_EARLY_RANKING_RESEARCH_DEFERRED`; historical R3H remains
`RANKING_OVERFIT_DETECTED`. See reports 66 and 68.

## Historical R3G Status

`RANKING_OVERFIT_DETECTED` (superseded by the Task 28A-R3H addendum below)

## Authoritative Four-cell Result

All cells used the same production retrieval entry, keyword-only mode,
`top_k=5`, three warmups, three performance runs, concurrency 1,
`persist_result=false`, `enable_llm=false`, and `allow_real_api=false`.

| Corpus / dataset | R@1 | R@3 | R@5 | MRR | nDCG@5 | Citation support | Failed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Pre-import / v1 | .750000 | .964286 | 1.000000 | .854167 | .891228 | 1.000000 | 0 |
| Pre-import / v2 | .785714 | .964286 | 1.000000 | .877976 | .909086 | 1.000000 | 0 |
| Post-import / v1 | .392857 | .714286 | .821429 | .560714 | .626207 | .821429 | 5 |
| Post-import / v2 | .464286 | .857143 | 1.000000 | .676786 | .758083 | 1.000000 | 0 |

No pre-import regression occurred. The post-import v2 result preserves full
Top-5 retrieval, citation validity/support, required-point coverage, safety,
abstention, and scope isolation, but R@1, R@3, MRR, and nDCG@5 remain below the
frozen early-ranking thresholds. Full formal acceptance must not be claimed.

## Reviewed-case Ranks

| Case | Best accepted rank | Expert-preferred rank |
| --- | ---: | ---: |
| HUAWEI-MODEL-002 | 1 | 1 |
| HUAWEI-INSULATION-004 | 2 | 4 |
| HUAWEI-COMM-002 | 2 | 4 |
| HUAWEI-TEMP-001 | 4 | combined chunks at 2 and 4 |
| HUAWEI-GRID-003 | 1 | 5 |

## Coverage and Browser

- Formal imported-document own-citation coverage: `10/10` passed.
- Amphenol title/model/content coverage: `3/3` passed.
- Generic alarm query returned the real inverter alarm reference with zero
  Sungrow citations.
- Authenticated headless-browser acceptance passed for five reviewed cases and
  the visible Amphenol citation panel.
- Citation detail traced to real document records and non-empty stored chunks.
- Browser console errors: `0`; authenticated API failures: `0`.

## Performance

- Final post-import v2 aggregate P50: `2178.977 ms`.
- Final post-import v2 aggregate P95: `3074.891 ms`.
- Pre-change P95: `6224.023 ms`.
- P95 change: `-50.5964%`.
- The `6000 ms` target and no-regression limit are both satisfied.

## Integrity and Verification

- Formal counts: 382 documents, 5,728 chunks, 2,598 QA records, 312
  diagnoses, 138 tasks, 221 devices, 414 media, 27 multimodal cases, 126
  contributions, 15 corrections, 34/34 KG nodes/edges, 136/12 SOP
  templates/executions, 1,463 users, 676 provider logs, and 88 vector runs.
- Formal Huawei Scope: 1,558 eligible chunks; pre-import Scope: 621.
- Every protected-table and Scope delta: `0`.
- PostgreSQL write probes: rejected on both read-only instances.
- Alembic: `20260712_0015`; no migration executed.
- Frozen v1 SHA-256:
  `9d2400a26f2a50ea3894b46ee2d5e2f88392ee1a539695a9467490e6d9ff20b0`.
- Expert-v2 SHA-256:
  `f9a000f45fd12571adebea90b52b97cf4cf5fe9dba01a8c33f80de5b2db68d68`.
- Backend compile passed; 50 new generic tests plus 4 related cache/hydration
  tests passed.

## Remaining Work

Early ranking on the expanded formal corpus remains the sole functional
blocker. A future task needs a broader independently reviewed training/dev
corpus and a fresh untouched holdout before activating generic ranking changes.
It must not tune against the frozen 30 cases or the consumed R3G holdout.

## Final Teardown

The task-started formal PostgreSQL process on `55432`, pre-import comparison
process on `55434`, and temporary FastAPI process on `8013` were stopped.
Ports `55432`, `55433`, `55434`, and `8013` were confirmed non-listening. The
Windows service `postgresql-x64-16` remains `Stopped / Disabled`.

## R3H Final Acceptance Addendum

Task 28A-R3H is `RANKING_OVERFIT_DETECTED`, not formal acceptance. The new Dev
passed, but the fresh Holdout was executed exactly once and failed R@3, R@5,
citation support, scope isolation, and failed-case gates. Frozen four-cell
results also failed pre-import no-regression and post-import v2 ranking gates.

Formal 10/10 coverage, Amphenol 3/3, 11/11 safety/scope regression, P95
`3054.218 ms`, 10/10 browser checks, zero console/API errors, zero database
writes, zero QA/provider/vector deltas, unchanged v1/v2 hashes, and zero
production fixture leakage all passed. These supporting passes do not override
the failed independent and frozen ranking gates.

R3H final cleanup stopped temporary FastAPI and PostgreSQL instances; ports
`8028`, `9338`, `55432`, `55433`, and `55434` were free, and the Windows
PostgreSQL service remained `Stopped / Disabled`.

## R3I Blocked Addendum

Task 28A-R3I could not safely activate the historical R3G product candidate or
rerun functional gates because the task-start tree already contained an
unfinished merge with eight unresolved paths. The current-source compile,
frontend build, regression, isolated workflow, and formal API/browser gates
were not passed. Formal data-only checks still confirmed 10/10 imported
documents, 937 chunks, exact protected counts, and zero writes. This addendum
does not supersede historical metrics and does not grant formal acceptance.
