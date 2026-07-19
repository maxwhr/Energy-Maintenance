# Task 25B-R2-U3 Pilot 恢复准备报告

## Task 25B-R2-U3-R2 当前判定

- 文档审核：首批 3 份 FAQ 已人工批准；3 份非预期长篇手册已审计化撤回。
- Corpus：`CORPUS_BLOCKED`，approved official documents=3，active formal chunks=3/300。
- Benchmark：本任务未执行专家审核，未写 `expert_verified`。
- Pilot index：blocked，`pilot_r2` active vectors=0。
- 正式全量重建：`TASK25B_ALLOW_FULL_REINDEX=false`，未执行。

## DashVector 边界

没有调用真实 Embedding 或 DashVector，没有新建/删除 Collection 或 Partition，没有修改默认 Partition。SmartLogger 当前解析版本被明确排除在 Pilot 之外。

## 恢复顺序

1. 人工逐份审核第二批最多 5 份代表性 FAQ。
2. 每批后运行 `check_task25b_r2_u3_corpus_gate.py --resume-after-document-approval`。
3. SmartLogger 先创建并抽检新的 parse/chunk 版本，保留原始文档和 Chunk；不得直接批准当前版本。
4. active formal Chunk 达到 300 后暂停扩充，再进行 Benchmark 双人审核。
5. 只有 Corpus 与 Benchmark 门禁全部通过后，才可由用户显式授权 `pilot_r2` 索引；全量重建继续禁用。

<!-- TASK25B_R3_DEV_BEGIN -->
## Task 25B-R2-U3-R3-DEV 中文工程 Pilot 更新

- 中文 Corpus Gate：`CHINESE_CORPUS_GATE_PASSED`，16 份文档、1262 个当前 Chunk。
- 开发工程审批与真实专家审批严格分离；`expert_verified=false`。
- 英文保留但不进入默认检索或 `pilot_r2`。
- Pilot 索引：1262 upserted；恢复阶段未重复索引，正式全量重建未执行。
- 质量门原 run 已完整产生 600/600 条结果；最终判定 `DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED`。
- 中断来自 Codex 模型容量，不是项目服务故障；恢复时未重复工程审批。
<!-- TASK25B_R3_DEV_END -->
