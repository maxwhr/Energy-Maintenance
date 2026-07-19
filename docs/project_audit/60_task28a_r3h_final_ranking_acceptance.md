# Task 28A-R3H Final Ranking Acceptance

## R3I Direction-correction Addendum

This document is retained as historical ranking-research evidence only.
Current engineering status is `ENGINEERING_EARLY_RANKING_RESEARCH_DEFERRED`,
and the R3I correction is `R3H_ABLATION_DETOUR_STOPPED`. No R3I Holdout was
run or rerun, and no post-Holdout tuning occurred.

The historical R3H conclusion below remains `RANKING_OVERFIT_DETECTED`; it
does not block the separately proven Huawei product functional status
`FORMAL_HUAWEI_RAG_FUNCTIONAL_ACCEPTANCE_PASSED` on the restored R3G safe
baseline. R3H Recall@1/3, MRR, and nDCG must not be claimed as passed.

## Historical R3H Status

`RANKING_OVERFIT_DETECTED`

The new independent Dev gate passed, but the one-shot independent Holdout did
not pass every mandatory metric. No rule or weight was changed after Holdout
execution.

## Independent Evaluation

| Dataset | Cases | R@1 | R@3 | R@5 | MRR | nDCG@5 | Citation support | Scope | Failed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| R3H Dev | 115 | .866667 | .952381 | .980952 | .909365 | .927229 | .980952 | 1.000000 | 2 |
| R3H Holdout | 60 | .800000 | .840000 | .880000 | .826667 | .839846 | .880000 | .700000 | 9 |

Dev SHA-256:
`76b17d676c9d68cf9edb6a1217e82187ee912125e025ca361822460075148dcc`.
Holdout SHA-256:
`5b8d2bdea0155d6f3141f99e9ce0f2182804fbc5cc131161919df4a3419a6eba`.
The Holdout evaluation count is exactly one.

## Frozen Four-cell Acceptance

| Corpus / dataset | R@1 | R@3 | R@5 | MRR | nDCG@5 | Citation support | Failed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Pre-import / v1 | .678571 | .892857 | .964286 | .797619 | .839857 | .964286 | 1 |
| Pre-import / v2 | .714286 | .892857 | .964286 | .815476 | .853038 | .964286 | 1 |
| Post-import / v1 | .500000 | .678571 | .785714 | .596429 | .643217 | .964286 | 6 |
| Post-import / v2 | .571429 | .785714 | .928571 | .688690 | .747884 | .964286 | 2 |

All cells retained citation validity `1.000000`, safety `1.000000`, Scope
isolation `1.000000`, and cross-vendor pollution `0`. Pre-import v1/v2 did not
meet their frozen no-regression baselines, and post-import v2 missed the
mandatory ranking and evidence-completeness gates.

## Performance, Coverage, and Browser

- Post-import v2 median P50/P95: `2102.024/3054.218 ms`.
- Maximum post-import v2 P95: `3091.330 ms`, below `3536.125 ms`.
- Warm-cache Scope hydration SQL maximum: `0` per query; cache-miss contract:
  at most one Scope SQL query.
- Formal imported-document coverage: `10/10`.
- Amphenol title/model/content coverage: `3/3`.
- Safety, abstention, and Scope regression: `11/11`.
- Browser: `10/10` read-only cases; console errors `0`; authenticated API
  4xx/5xx `0`; citation document/Chunk/page-or-section visible; Sungrow
  citation pollution `0`.

The browser used the current static frontend after a fresh build/install. A
test-only CDP interception changed every retrieval payload to
`persist_result=false`, `enable_llm=false`, and `allow_real_api=false`.

## Integrity

Formal counts remained 382 documents, 5,728 chunks, 2,598 QA records, 312
diagnoses, 138 tasks, 221 devices, 414 media, 27 multimodal cases, 126
contributions, 15 corrections, 34/34 KG nodes/edges, 136/12 SOP
templates/executions, 1,463 users, 676 provider logs, and 88 vector runs.
Every protected count delta, Scope delta, QA delta, provider delta, vector-run
delta, and database-write count is zero. Both database write probes were
rejected by PostgreSQL read-only transactions.

Frozen v1 and v2 SHA-256 values remain respectively
`9d2400a26f2a50ea3894b46ee2d5e2f88392ee1a539695a9467490e6d9ff20b0`
and
`f9a000f45fd12571adebea90b52b97cf4cf5fe9dba01a8c33f80de5b2db68d68`.

## Decision

The implementation proves and repairs score-provenance loss and non-monotonic
reranking, but it is not accepted for formal Huawei RAG delivery. The next
ranking task requires a new untouched Holdout and must begin from the nine
failed Holdout categories without using their labels for further tuning in
this task.

## Final Teardown

The task-started FastAPI process and both PostgreSQL instances were stopped.
Ports `8028`, `9338`, `55432`, `55433`, and `55434` were confirmed free. The
Windows service `postgresql-x64-16` ended `Stopped / Disabled`; browser tabs
were finalized and the temporary JWT was removed without being written to an
artifact.

## R3I Safety Disposition Addendum

R3I did not retain any attempted ranking change. The seven authorized retrieval
files were restored to their exact R3I task-start hashes after a pre-existing
unfinished merge was found to block compile, test collection, and new backend
startup. Historical R3H status remains `RANKING_OVERFIT_DETECTED`, and early
ranking research remains `ENGINEERING_EARLY_RANKING_RESEARCH_DEFERRED`. No
consumed Holdout was rerun or used for tuning.
