# Task 25B-R1 Retrieval Quality Tuning Report

## Status

- Result: PASSED on the single frozen engineering-controlled test_v2 run.
- test_v1 is exposed and is used only for error analysis and regression.
- test_v2 frozen SHA-256: `2cdf413a1ca58fc77ea3ca64f117f1b909c6bd2ab8ca556ca2fd2bba25bfbe5b`.
- train/dev/test_v2 source-document overlap: zero.
- No post-blind tuning or repeat blind run is allowed.

## Corpus

- Controlled documents: 24
- Active chunks: 192
- Hard negatives: 48
- Splits: train=72, dev=54, test_v2=54
- Domain benchmark drafts: 30; status remains draft/review_required, not expert_verified.

## Blind comparison

| Mode | R@5 | R@10 | MRR | nDCG@10 | p95 ms |
|---|---:|---:|---:|---:|---:|
| keyword | 1.000000 | 1.000000 | 0.981481 | 0.986331 | 469.762 |
| vector | 0.574074 | 0.685185 | 0.530504 | 0.566117 | 1757.336 |
| hybrid | 0.925926 | 0.925926 | 0.839506 | 0.861407 | 838.466 |
| hybrid_rerank | 0.925926 | 0.925926 | 0.839506 | 0.861407 | 723.341 |
| adaptive | 1.000000 | 1.000000 | 0.981481 | 0.986331 | 704.712 |

Adaptive protects strong keyword evidence, uses vector candidates for semantic/visual routes, and falls back visibly. Reranker is disabled because dev nDCG gain was 0.000000.

## Boundaries

The production default remains `keyword`. Formal full reindex was not executed. LoongArch + Kylin hardware validation remains outstanding. No package or Git commit was created.

## Final verification

- Backend compileall: passed.
- Pytest: 30 passed.
- Alembic: `20260601_0009 (head)`; no new migration.
- Security/RBAC: passed; RBAC matrix 40 checks, 0 failed.
- Agent and conversion regression: passed; deterministic vector flow is explicitly test-only.
- Frontend audit/build/type-check: passed; 0 npm vulnerabilities.
- Browser: passed; viewer evaluation/index writes returned 403; console/page/network errors were 0.
- Current-code final smoke: 23/23 passed on temporary port 8013 after OpenAPI R1-path verification. The pre-existing non-reload 8010 process was not used or stopped.


<!-- TASK25B_R2_BEGIN -->
## Task 25B-R2 正式知识 Pilot 状态

- 状态：`BLOCKED_CONFIG`；正式可用语料只有 6 份文档、11 个 active Chunk，未达到 300。
- 独立 Pilot Collection `energy_kn_te_v4_1024_pilot1` 创建被服务商 2 个 Collection 配额阻断；未删除或复用现有 Collection。
- 已生成 150 条 `draft` 候选；`expert_verified=0`，未冻结或运行 `official_pilot_test_v1`。
- 默认 Collection 与 `keyword` 策略未改变；`TASK25B_ALLOW_FULL_REINDEX=false`，全量重建决策为 NO-GO。
- 本任务未打包、未提交 Git；LoongArch/Kylin 仍未实机验收。
<!-- TASK25B_R2_END -->
