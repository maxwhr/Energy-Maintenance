# Task 25B-R1 Blind Evaluation Report

- Dataset: test_v2, frozen before tuning.
- Frozen hash: `2cdf413a1ca58fc77ea3ca64f117f1b909c6bd2ab8ca556ca2fd2bba25bfbe5b`
- Formal run number: 1
- Rerun allowed: false
- PostgreSQL evaluation run: `6b3f4d02-89cc-4b94-a084-8408bb197134`
- Quality gate: PASSED
- Label leakage scan: PASSED

Adaptive final metrics: R@5=1.000000, R@10=1.000000, Precision@5=0.274074, MRR=0.981481, nDCG@10=0.986331, MAP=0.981481, citation validity=1.000000, no-answer F1=1.000000, leakage=0.000000, category minimum R@5=1.000000.

This is an engineering-controlled blind result, not an expert-verified enterprise benchmark claim. No tuning was performed after the result.

The test_v2 formal run count is permanently recorded as 1 and rerun is disabled. The production default remains `keyword`; `adaptive` is eligible only for a bounded pilot with visible keyword fallback. Full formal knowledge reindex was not executed.


<!-- TASK25B_R2_BEGIN -->
## Task 25B-R2 正式知识 Pilot 状态

- 状态：`BLOCKED_CONFIG`；正式可用语料只有 6 份文档、11 个 active Chunk，未达到 300。
- 独立 Pilot Collection `energy_kn_te_v4_1024_pilot1` 创建被服务商 2 个 Collection 配额阻断；未删除或复用现有 Collection。
- 已生成 150 条 `draft` 候选；`expert_verified=0`，未冻结或运行 `official_pilot_test_v1`。
- 默认 Collection 与 `keyword` 策略未改变；`TASK25B_ALLOW_FULL_REINDEX=false`，全量重建决策为 NO-GO。
- 本任务未打包、未提交 Git；LoongArch/Kylin 仍未实机验收。
<!-- TASK25B_R2_END -->
