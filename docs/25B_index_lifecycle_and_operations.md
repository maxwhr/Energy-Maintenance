# Task 25B 向量索引生命周期与运维

## 事实源与集合

PostgreSQL 是事实源；DashVector 是可重建召回索引。

- logical knowledge collection：`energy_maintenance_knowledge_te_v4_1024_v1`
- physical knowledge collection：`energy_kn_te_v4_1024_v1`
- logical media collection：`energy_maintenance_media_te_v4_1024_v1`
- physical media collection：`energy_media_te_v4_1024_v1`
- embedding version：`text-embedding-v4-1024-v1`

## 生命周期规则

- 只索引 `approved + active + parsed` 文档和 active chunk。
- content hash、embedding model/dimension/version 或 collection 变化触发 stale/rebuild。
- stable vector ID 基于 collection/namespace/chunk UUID 哈希，符合 DashVector 64 字符和字符集限制。
- query 先 metadata 过滤，后 PostgreSQL 批量二次校验。
- pending、rejected、archived、deleted 不得进入最终结果。
- 索引 run 持久化 total/succeeded/skipped/failed 和安全 metadata；不保存或记录完整向量。

## 运维命令

```powershell
uv run python scripts/check_task25b_index_lifecycle.py
uv run python scripts/check_task25b_index_lifecycle.py --allow-real-api --execute-test-only
uv run python scripts/check_task25b_full_reindex.py
```

默认是 dry-run/test-only。全量 approved 重建必须显式 `--execute --allow-real-api` 且环境 `TASK25B_ALLOW_FULL_REINDEX=true`。本次全量开关为 false，没有执行正式知识全量重建。

## 当前验收

8 个 `Task25B_` chunk 真实索引成功，8/8 succeeded、0 failed。PostgreSQL FK 约束下孤儿索引行计数为 0；本次没有声称完成 DashVector 全集合 ID 扫描，因此 `external_collection_scan_performed=false`，外部孤儿全量核对仍是运维待办。

<!-- TASK25B_R1_BEGIN -->
## Task 25B-R1 controlled blind acceptance (2026-07-11T02:32:50.109583+00:00)

- test_v1 is exposed and regression-only; test_v2 is independently frozen with SHA-256 `2cdf413a1ca58fc77ea3ca64f117f1b909c6bd2ab8ca556ca2fd2bba25bfbe5b`.
- Corpus: 24 documents, 192 active chunks, 48 hard negatives.
- Adaptive blind metrics: R@5=1.000000, R@10=1.000000, MRR=0.981481, nDCG@10=0.986331, warm p95=704.712 ms.
- Reranker disabled: no measurable dev gain. Default retrieval strategy remains keyword.
- Canary uses an isolated partition because the provider collection quota is exhausted; v1 default partitions remain intact.
- Formal full reindex, package generation and Git commit were not executed. LoongArch real-machine testing remains outstanding.
<!-- TASK25B_R1_END -->


<!-- TASK25B_R2_BEGIN -->
## Task 25B-R2 正式知识 Pilot 状态

- 状态：`BLOCKED_CONFIG`；正式可用语料只有 6 份文档、11 个 active Chunk，未达到 300。
- 独立 Pilot Collection `energy_kn_te_v4_1024_pilot1` 创建被服务商 2 个 Collection 配额阻断；未删除或复用现有 Collection。
- 已生成 150 条 `draft` 候选；`expert_verified=0`，未冻结或运行 `official_pilot_test_v1`。
- 默认 Collection 与 `keyword` 策略未改变；`TASK25B_ALLOW_FULL_REINDEX=false`，全量重建决策为 NO-GO。
- 本任务未打包、未提交 Git；LoongArch/Kylin 仍未实机验收。
<!-- TASK25B_R2_END -->
