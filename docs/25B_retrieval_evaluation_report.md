# Task 25B 检索评测报告

## 数据集

- Engineering Controlled Benchmark：80 条，10 类，每类 8 条，`engineering_verified`。
- Competition Domain Benchmark Draft：30 条，由当前 approved 正式知识派生，状态保持 `draft`，metadata 标记 `review_required=true`，未写成 `expert_verified`。
- 拆分：train/dev/test；test split 只评估，不调权重。

类别覆盖设备型号、故障码、故障现象、章节定位、安全操作、图片 OCR、图片视觉描述、相似历史案例、无答案和干扰文档过滤。

## 真实 test split 结果

| Mode | R@5 | R@10 | MRR | nDCG@10 | Citation | Leakage | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| keyword | 0.90 | 0.90 | 0.82 | 0.838685 | 1.00 | 0 | 234.105 |
| vector | 0.75 | 0.90 | 0.388393 | 0.510056 | 1.00 | 0 | 10985.536 |
| hybrid | 0.90 | 0.90 | 0.58 | 0.654741 | 1.00 | 0 | 6883.964 |
| hybrid_rerank | 0.90 | 0.90 | 0.58 | 0.654741 | 1.00 | 0 | 4362.713 |

设备型号与故障码 exact accuracy 在 hybrid_rerank 上均为 1.00；error rate 为 0，fallback rate 为 0。

## 门禁结论

FAILED。

- 通过：Recall@5、型号/故障码 exact、leakage、citation validity、error rate、rerank 不下降超过 1%。
- 未通过：Recall@10、MRR、nDCG@10、在线 p95。

本报告不选择性展示最佳单次结果，也不把 keyword 的较好结果冒充 hybrid_rerank 结果。由于 nDCG 未达到目标，不声明精排带来提升。

完整 per-case 结果保存于 PostgreSQL `retrieval_evaluation_results`；runtime 只保存安全汇总，避免输出完整文档正文或向量。

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
