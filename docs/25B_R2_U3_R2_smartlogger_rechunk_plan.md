# Task 25B-R2-U3-R2 SmartLogger 重切分计划

生成时间：`2026-07-12T05:49:30.145617+00:00`

## 结论

- 两份 SmartLogger 原始文档及 642 个 Chunk 均保持不变；before/after 快照一致，`automatically_modified=false`。
- 两份文档均需重切分，且不得直接批准或进入 Pilot。
- 告警参考应按“一告警一结构化知识单元”重建；用户手册应按章节/语义小节重建。

## 原始质量分析

- `058ddd98-e3e8-44b5-a154-fb86923c3ff4`：原始 Chunk=150，页数=未写入，exact groups=25（额外 Chunk=25），near pairs=29，重复页眉候选=47，导航/页脚噪声=0/0，heading/page/locator=100.00%/0.00%/100.00%。
- `da7ee239-a195-4345-94d1-48a54085bf2c`：原始 Chunk=492，页数=未写入，exact groups=19（额外 Chunk=19），near pairs=41，重复页眉候选=19，导航/页脚噪声=0/0，heading/page/locator=100.00%/0.00%/100.00%。

告警参考候选：显式代码 25，命名告警 51，映射前结构化单元候选 76。这些候选必须先完成人工 code/name 对齐与去重，不把数量当作最终单元数。

### 告警字段出现情况（Chunk 数）

- alarm_code_chunks: 76
- alarm_name_chunks: 42
- severity_chunks: 27
- impact_chunks: 16
- cause_chunks: 25
- handling_step_chunks: 25
- safety_action_chunks: 23
- applicable_device_chunks: 4

## 告警参考重切分

每个单元必须同时保存：`alarm_code`、`alarm_name`、`severity`、`impact`、`possible_causes`、`handling_steps`、`safety_actions`、`applicable_models`、`source_page`、`source_section`。续表按告警码和 Cause ID 合并，严禁把代码、原因、建议拆成无上下文 Chunk。

## 用户手册重切分

按章节切分；清除重复页眉/页脚；目录和导航不进入正式检索；合并相邻短段；表格保持完整；安全警告绑定到对应步骤；超长章节只在语义边界继续拆分。

## 安全落地方式

创建新的 parse/chunk 版本并与原文档并存，完成人工抽检后再决定切换。不得覆盖或删除当前文档与 Chunk；本任务未执行批准、重切分、Embedding、DashVector 或 Pilot 索引。
