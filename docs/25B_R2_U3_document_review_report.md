# Task 25B-R2-U3 文档人工审核报告

## Task 25B-R2-U3-R2 当前状态

审核地址：http://127.0.0.1:8012/review

- 用户指定的 3 份代表性 FAQ 已由真实 admin 人工批准，均有 `pending_review → approved` 审计记录。
- 质量复核检测到 3 份非预期获批长篇手册（SUN2000、LUNA2000、SmartLogger3000）；已通过 expert/admin 限定的审计化撤回接口恢复为 `pending_review`，未直接修改数据库。
- 当前 approved 官方文档为 3，pending 官方文档为 31，active formal Chunk 为 3。
- 撤回文档均标记为 `REQUIRE_INDIVIDUAL_REVIEW`、`approved_for_pilot=false`、`pilot_index_excluded=true`。
- 两份 SmartLogger 长文档均在页面显示“必须逐份审核”，且当前解析版本被后端阻止批准进入 Pilot。

## 第二批建议（最多 5 份）

1. `ed7da861-c472-4bbe-8389-66d6fee05134` — The indicator is red.
2. `9cb20238-ef5f-4719-87db-94f57afba008` — The WiFi communication fails at night.
3. `6ae662ed-9382-4b96-95d7-acc7fb4d8250` — Do PV inverters need to be grounded?
4. `836cc336-8af6-4d81-9f43-86a59e794a73` — Checking Cable Connection when the Battery Fails to Be Upgraded.
5. `584adeaf-7221-4ab6-b191-749ce3c99c57` — 如何更换熔丝。

排除 SmartLogger、NEEDS_METADATA、marketing-only，以及与已批准中文 FAQ 重复的 3 份英文 FAQ。本报告未发起任何批准请求。

<!-- TASK25B_R3_DEV_BEGIN -->
## Task 25B-R2-U3-R3-DEV 中文工程 Pilot 更新

- 中文 Corpus Gate：`CHINESE_CORPUS_GATE_PASSED`，16 份文档、1262 个当前 Chunk。
- 开发工程审批与真实专家审批严格分离；`expert_verified=false`。
- 英文保留但不进入默认检索或 `pilot_r2`。
- Pilot 索引：1262 upserted；恢复阶段未重复索引，正式全量重建未执行。
- 质量门原 run 已完整产生 600/600 条结果；最终判定 `DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED`。
- 中断来自 Codex 模型容量，不是项目服务故障；恢复时未重复工程审批。
<!-- TASK25B_R3_DEV_END -->
