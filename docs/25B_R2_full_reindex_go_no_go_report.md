# Task 25B-R2 正式全量重建 Go / No-Go

## 决策

NO-GO。

## 未通过门禁

- 正式 Pilot Chunk 11/300。
- 独立 Pilot Collection 因服务商 Collection 配额 2/2 未创建。
- Pilot 索引和对账未执行。
- expert_verified 0/100，第二审核 0/20。
- official_pilot_test_v1 未冻结、未运行。
- Vector-heavy、Precision@5、Citation validity 无正式专家指标。
- 生命周期、Pilot 激活和真实回滚未执行。

## 解除阻断的条件

1. 补充并审核至少 300 个真实正式 Chunk，覆盖华为/阳光电源、手册/告警/SOP/案例/安全规程。
2. 提升 DashVector Collection 配额或由管理员明确提供新的独立 Cluster；不得删除现有 v1/R1 数据来腾配额。
3. 在前端由真实 expert/admin 完成至少 100 条审核，并由不同账户完成至少 20% 第二审核。
4. 重新创建新版本 Pilot，完成索引、对账、生命周期、受控切换/回滚和一次性 official Pilot 评估。

正式全量重建仍由 `TASK25B_ALLOW_FULL_REINDEX=false` 阻断，本任务未执行。

## U3 复核

结论仍为 NO-GO。候选规模已达到 34 份/1,161 Chunk，但批准与 active 数均为 0；expert_verified 0/100、second review 0/20。U3 没有新建 Collection，也没有借候选规模绕过正式全量重建门禁。

<!-- TASK25B_R3_DEV_BEGIN -->
## Task 25B-R2-U3-R3-DEV 中文工程 Pilot 更新

- 中文 Corpus Gate：`CHINESE_CORPUS_GATE_PASSED`，16 份文档、1262 个当前 Chunk。
- 开发工程审批与真实专家审批严格分离；`expert_verified=false`。
- 英文保留但不进入默认检索或 `pilot_r2`。
- Pilot 索引：1262 upserted；恢复阶段未重复索引，正式全量重建未执行。
- 质量门原 run 已完整产生 600/600 条结果；最终判定 `DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED`。
- 中断来自 Codex 模型容量，不是项目服务故障；恢复时未重复工程审批。
<!-- TASK25B_R3_DEV_END -->

<!-- TASK25B_R3_DEV_R1_BEGIN -->
## Task 25B-R3-DEV-R1 检索治理更新

- v1 run `f1941ec2-9878-45a1-b554-8d9f2f2ec911` 失败且保留；v2 run `3e40e25f-f1f1-4146-9e1e-629d2ce76045` 独立保存。
- Benchmark 数据集状态：`BENCHMARK_DATASET_READY`；质量门状态：`QUALITY_GATE_FAILED`，二者不得混淆。
- Scope：`chinese_engineering_pilot_r2`；Canary：`CANARY_PASSED`；正式 v2：`DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED`。
- Pilot 对账：1262/1262，re-embedded=0、re-upserted=0。
- 工程审批不等于专家验证；正式全量重建未执行；不打包、不提交 Git。
<!-- TASK25B_R3_DEV_R1_END -->

<!-- Task25B-R3-DEV-R2 -->

R2 did not execute a formal full rebuild, clear pilot_r2, or rebuild the 1,262 vectors.

<!-- TASK25B_R3_DEV_R3 -->
## Task 25B-R3-DEV-R3 semantic recall diagnosis

- R2 Canary remains `CANARY_FAILED` and its artifacts are preserved read-only.
- Raw Chunk representation dilution was diagnosed with train/dev-only embedding pairs; DashVector filtering and mapping were not the root cause.
- An isolated `pilot_r3_semantic` A/B partition was created with 416 source-only anchors. `pilot_r2`, the default partition, and the original 1,262 vectors were not changed.
- The independent Canary failed: semantic Candidate Recall@50 = 0.444444, below 0.90. `test_v3_1` was not created or frozen and no formal quality run or full reindex occurred.
- `expert_verified=false`; no package, Git commit, or LoongArch physical verification occurred.
# R4 impact

R4 is an isolated engineering experiment and does not change the R2 full-reindex decision. A staged or full reindex remains prohibited unless the R4 Grounded Canary and any subsequently authorized formal v4 quality gate pass their unchanged thresholds.
