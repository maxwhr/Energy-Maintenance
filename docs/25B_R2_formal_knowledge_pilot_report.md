# Task 25B-R2 正式知识 Pilot 总报告

- 最终状态：BLOCKED_CONFIG
- 正式语料：6 份文档、11 个真实 active Chunk。
- synthetic/controlled 补数：0。
- 独立 Pilot Collection：energy_kn_te_v4_1024_pilot1；状态 BLOCKED_PROVIDER_COLLECTION_QUOTA。
- 正式默认 Collection：energy_kn_te_v4_1024_v1，未修改。
- Pilot 索引：BLOCKED，upsert 0。
- 专家候选：150；全部 draft。
- expert_verified：0；second reviewed：0。
- official_pilot_test_v1：未冻结、未运行；一次性运行次数 0。
- 生命周期：BLOCKED_NO_INDEPENDENT_PILOT_INDEX。
- Pilot 切换：BLOCKED_NO_PILOT_INDEX；路由从未改变。
- 回滚：NOT_REQUIRED_ROUTE_NEVER_CHANGED；Base 始终保持。
- 正式全量重建：NO-GO，未执行。
- LoongArch/Kylin：仅静态兼容，不宣称实机通过。
- 打包/Git commit：未执行。

## 受控工程数据与正式 Pilot 边界

Task 25B-R1 的 24 份受控文档与 192 个 Chunk 只保留为工程回归基线。本任务没有用它们填充正式 Pilot 的 300 Chunk 门槛，也没有重跑 R1 一次性盲测。

## 阻断项

- formal corpus has 11 eligible chunks; 300 required
- independent Pilot Collection creation blocked by provider quota 2
- expert_verified is 0/100 and second review is 0/20
- official Pilot dataset and one-time run were not executed

## U3 状态补充

U3 已把正式候选扩充到 34 份 pending 文档和 1,161 个预计 Chunk，并加入显式告警/故障知识与快速审核页。当前批准文档和 active formal Chunk 仍为 0，Benchmark 专项候选 200 条但 expert/second review 均为 0。既有 `energy_kn_te_v4_1024_v1/pilot_r2` 保留，Pilot 索引仍由人工门禁阻断。

<!-- TASK25B_R3_DEV_BEGIN -->
## Task 25B-R2-U3-R3-DEV 中文工程 Pilot 更新

- 中文 Corpus Gate：`CHINESE_CORPUS_GATE_PASSED`，16 份文档、1262 个当前 Chunk。
- 开发工程审批与真实专家审批严格分离；`expert_verified=false`。
- 英文保留但不进入默认检索或 `pilot_r2`。
- Pilot 索引：1262 upserted；恢复阶段未重复索引，正式全量重建未执行。
- 质量门原 run 已完整产生 600/600 条结果；最终判定 `DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED`。
- 中断来自 Codex 模型容量，不是项目服务故障；恢复时未重复工程审批。
<!-- TASK25B_R3_DEV_END -->
