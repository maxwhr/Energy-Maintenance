# Task 28A-R3I Rerun Product Functional Acceptance

## Authoritative Status

`FORMAL_HUAWEI_RAG_FUNCTIONAL_ACCEPTANCE_PASSED`

The product functional gate passed on the restored R3G safety baseline. Early
ranking research is explicitly non-blocking and deferred under
`ENGINEERING_EARLY_RANKING_RESEARCH_DEFERRED`.

## Direction Correction

- `R3H_ABLATION_DETOUR_STOPPED`.
- C0 is retained only as historical `CURRENT_R3H_PRODUCT_GATE_FAILED` evidence.
- C1-C3 completed as read-only process-local experiments before the stop; C4
  was interrupted and C5 never started.
- No C1-C5 process modified production files.
- No Holdout was run or rerun in R3I, and no result was used for tuning.
- Reconciliation: `.runtime/task28a-r3i/code_selection/r3h_detour_reconciliation.json`.

## Accepted Product Baseline

The default path is
`A1_scope_snapshot_plus_A2_precomputed_features_safe_rollback`. Six production
retrieval files match the SHA-256 verified R3G recovery snapshot. Query signal
extraction additionally retains the R3I distinction between a safety inquiry
and an instruction to perform live electrical work. The existing unsafe-request
abstention path remains enabled; no R3H ranking weight remains active.

## Product Gate

| Gate | Result |
| --- | ---: |
| Post-import/v2 Recall@5 | 1.000000 |
| Citation validity | 1.000000 |
| Citation support | 1.000000 |
| Required-point coverage | 1.000000 |
| Failed cases | 0 |
| Scope isolation | 1.000000 |
| Safety coverage | 1.000000 |
| Abstention | 1.000000 |
| Cross-manufacturer citations | 0 |
| Fabricated citations | 0 |
| Pending/archived citations | 0 |
| P50 / P95 | 1763.571 / 2485.602 ms |
| Maximum latency | 4190.699 ms |

Recall@1 `.464286`, Recall@3 `.857143`, MRR `.676786`, and nDCG@5
`.758083` are reported as non-blocking early-ranking diagnostics only.

## Functional Verification

- Formal imported Huawei document coverage: `10/10`.
- Amphenol title/model/content coverage: `3/3`.
- Safety/Scope/Abstention regression: `11/11`.
- Isolated upload lifecycle: parsed -> pending excluded -> approved self-cited
  -> archived excluded; `1` real Chunk; QA delta `0`.
- Isolated Provider/embedding/vector deltas: `0`.
- Formal counts remained documents `382`, chunks `5728`, QA `2598`, Provider
  logs `676`, vector runs `88`.
- Formal write probe rejected with SQLSTATE `25006`; formal writes/deletes `0`.
- Browser: admin login, Dashboard, real retrieval/citations, six product pages,
  logout, viewer write-menu hiding, and forced `/403` passed; console errors `0`.
- Focused product tests: `61 passed`.
- Backend compileall, frontend TypeScript/build, static installation, and npm
  audit (`0` vulnerabilities) passed.
- Secret scan passed with `blocking_count = 0`; no secret value was printed.

## Integrity

- Alembic remains `20260712_0015`; no migration was created or executed.
- Frozen v1 SHA-256 remains
  `9d2400a26f2a50ea3894b46ee2d5e2f88392ee1a539695a9467490e6d9ff20b0`.
- Expert v2 SHA-256 remains
  `f9a000f45fd12571adebea90b52b97cf4cf5fe9dba01a8c33f80de5b2db68d68`.
- No external Provider, Cloud LLM, embedding, vector rebuild, or formal login
  was used.
