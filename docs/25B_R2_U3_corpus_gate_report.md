# Task 25B-R2-U3 Corpus Gate 报告

## Task 25B-R2-U3-R2 复核结果

`CORPUS_BLOCKED`，这是 3 份首批 FAQ 人工批准后的真实门禁结果。

| 门禁 | 要求 | 当前 active/approved | 缺口 |
|---|---:|---:|---:|
| approved official documents | 15 | 3 | 12 |
| active formal chunks | 300 | 3 | 297 |
| inverter documents | 5 | 2 | 3 |
| storage documents | 2 | 1 | 1 |
| SmartGuard/管理/通信 | 2 | 0 | 2 |
| document types | 5 | 1 | 4 |
| alarm code + named alarm | 20 | 1 | 19 |
| troubleshooting sections | 30 | 4 | 26 |
| safety sections | 20 | 0 | 20 |

未知来源、营销泄漏、pending 泄漏、重复泄漏均为 0。当前仅覆盖 `FAQ_TROUBLESHOOTING`，active formal Chunk 仍远低于 300；`pilot_index_allowed=false`，不得执行 Pilot 索引。

<!-- TASK25B_R3_DEV_BEGIN -->
## Task 25B-R2-U3-R3-DEV 中文工程 Pilot 更新

- 中文 Corpus Gate：`CHINESE_CORPUS_GATE_PASSED`，16 份文档、1262 个当前 Chunk。
- 开发工程审批与真实专家审批严格分离；`expert_verified=false`。
- 英文保留但不进入默认检索或 `pilot_r2`。
- Pilot 索引：1262 upserted；恢复阶段未重复索引，正式全量重建未执行。
- 质量门原 run 已完整产生 600/600 条结果；最终判定 `DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED`。
- 中断来自 Codex 模型容量，不是项目服务故障；恢复时未重复工程审批。
<!-- TASK25B_R3_DEV_END -->
