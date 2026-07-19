# Task 25B-R3-DEV-R5-R4-MM 确定性查询理解统一报告

最终状态：`QUERY_AWARE_GROUNDED_RAG_R4_QUALITY_GATE_FAILED`

结论先行：确定性 Query-Aware RAG 在一次 Train/Dev 校准后明显改善，并满足引用、无答案、安全、错误率和全部性能门，但 iteration 2 仍未达到 Candidate Recall@50、MRR、nDCG@10 和 intent accuracy 四个硬门。因此 Formal 测试集没有创建、冻结或运行；当前不得进入 Task 25C。MiniMax 仅作为可选歧义裁决器，Canary 中未带来检索质量增益，且 structured success 与 p95 也未达到可选组件目标。安全降级对两个失败案例保持 100% 无损。

## 1. Codex 容量中断与恢复

- 中断原因为 Codex 所选模型容量不足（`Selected model is at capacity`），不是项目代码、MiniMax、DashVector、Embedding、PostgreSQL、前端或确定性查询理解故障。
- 恢复分类：`CANARY_STATE_INCONSISTENT`。原 iteration 1 进程已结束，完整 artifact 被保留；没有启动重复 iteration 1 run，也没有重复执行已成功 case/config。
- 原 artifact 每配置 81 条，而恢复指令声明 76 条。该差异被记录为不可变现场证据：iteration 1 共 162 条、missing=0、duplicate=0；iteration 2 使用校准后的 76 条执行集，共 152 条。
- Snapshot、30 条标签审计、55 条确定性 Probe、20 条歧义候选 Probe、20 次真实 MiniMax Probe 均未重跑。
- iteration 2 使用 `(iteration, configuration, case_id)` 唯一键、进程锁、逐案例原子 checkpoint 和 `--only-missing` 恢复；checkpoint 最终同时保留 iteration 1 的 162 条与 iteration 2 的 152 条唯一记录。

## 2. R5-R3-MM 冻结基线

- 来源：`Task 25B-R3-DEV-R5-R3-MM`；状态：`QUERY_UNDERSTANDING_CONTRACT_NOT_READY`；运行时选择：`deterministic`。
- R5-R3-MM MiniMax-M3 structured=73.33%，intent=63.33%，canonicalization=63.33%，p95=4461.794 ms。
- MiniMax-M2.7-highspeed structured=0.00%，p95=4513.682 ms。
- 受保护的 R5-R3-MM 报告与机器 artifact SHA-256 均未变化。

## 3. A/B 标签独立审计

- 审计 30 条，唯一 case ID 校验通过；修订 3 条：`ab16`、`ab19`、`ab27`。
- 审计依据为 `human_rule_audit_only`；没有使用 MiniMax 输出，没有使用正式测试标签，旧标签源文件 SHA-256 前后一致。

- `ab16`：`ALARM`/clarify=true → `TROUBLESHOOTING`/clarify=true。证据：“怎么处理”明确请求处置/排查动作，意图应为 TROUBLESHOOTING；指代的告警代码或名称缺失，因此仍须追问。
- `ab19`：`COMMUNICATION`/clarify=false → `COMMUNICATION`/clarify=true。证据：“RS485通信中断”仅描述现象，未说明要查询原因、步骤或恢复验证；应补充 REQUESTED_ACTION。
- `ab27`：`CAUSE`/clarify=false → `CAUSE`/clarify=true。证据：原因意图明确，但“告警”没有代码或名称，无法限定要检索的具体告警；应补充 ALARM_CODE。

## 4. 确定性查询理解与 canonicalization

- 实现系统侧信号提取、意图识别、canonicalization、型号/告警/数字/条件保留和会话补充合并。
- Fast Path 继续兼容：显式 `retrieval_mode=fast` 不启用扩展查询理解，避免改变既有 API 语义。
- Probe：55 条；intent=100.00%；canonicalization=100.00%；clarification=100.00%。
- 型号/告警幻觉=0/0；外部调用=0；p95=0.486 ms。

## 5. 歧义候选与追问模板

- Ambiguity Options Probe：20 条，正确解释覆盖=100.00%，最大候选数=4。
- 知识答案泄漏=0；expected label 泄漏=0。
- 追问由确定性模板生成；MiniMax 不生成检索查询、维修答案、型号或告警码。

## 6. MiniMax 歧义裁决 Probe

- 真实 MiniMax-M3 调用 20 次，structured success=19/20（95.00%），唯一失败安全回退。
- unknown interpretation IDs=0；型号/告警幻觉=0/0；失败安全降级=100.00%；p95=4580.357 ms。
- 该 Probe 达到可选组件目标，但其结果不替代端到端 Canary，也没有被用于修改标签。

## 7. Canary iteration 1

- 数据集：`task25b_r3_dev_r5_r4_mm_train_dev_v1`；不可变 artifact 为 81 条/配置、2 个配置、162 条结果；missing=0，duplicate=0。
- 由于 predecessor artifact 与恢复指令的 76 条口径不一致，现场分类为 `CANARY_STATE_INCONSISTENT`，但 artifact 本身唯一且完整，因此未重跑。
- deterministic-only 状态：`QUERY_AWARE_GROUNDED_RAG_R4_QUALITY_GATE_FAILED`；失败门：candidate_recall_at_50, recall_at_5, recall_at_10, mrr, ndcg_at_10, intent_accuracy, canonicalization, clarification_precision, context_merge, hallucinated_alarm_zero。
- 核心指标：Candidate R@50=75.00%，R@5=73.21%，R@10=73.21%，MRR=0.519940，nDCG@10=0.572519，intent=83.95%，canonicalization=86.42%，clarification precision=50.00%，context merge=0.00%，告警幻觉=1。
- optional MiniMax 端到端指标与 deterministic-only 相同，quality gain 全为 0。

## 8. 唯一一次 Train/Dev 校准

- 执行次数：1；状态：`ONE_TRAIN_DEV_CALIBRATION_RECORDED`。
- 标签修改=False；rerank weights 修改=False；confidence/quality gate 阈值修改=False/False。
- 通用修改：外层请求短语优先；补充口语 action/procedure 词表；RS232/RS485 不再误识别为告警码；具体会话症状可解除通用缺失症状；alarm names/numbers 纳入会话槽位。
- 执行集从 81 调整为 76，仅去除 5 条重复 no-answer；仍保留 8 条 no-answer（3 条原始 + 5 条实体冲突）。没有使用正式测试数据，没有增加语料或重新索引。
- 向量变化：re-embedded=0，re-upserted=0，collection/partition changes=0/0。

## 9. Canary iteration 2 与确定性质量门

- 数据集：`task25b_r3_dev_r5_r4_mm_train_dev_v1_calibrated_execution_v2`；run ID：`r5r4mm-canary-iteration2-resume2`；76 条/配置，expected/actual=152/152，missing=0，duplicate=0。
- deterministic-only 状态：`QUERY_AWARE_GROUNDED_RAG_R4_QUALITY_GATE_FAILED`；失败门：candidate_recall_at_50, mrr, ndcg_at_10, intent_accuracy。
- 失败案例观测分布：`{"candidate_miss": 17, "canonicalization": 4, "cases_with_observed_failure": 17, "clarification": 1, "intent": 4}`。该分布是逐案例可观测错误分类，不替代总体门禁。

| 指标 | iteration 2 | 硬门 | 结果 |
|---|---:|---:|---|
| Candidate Recall@50 | 91.07% | >=95% | FAIL |
| Recall@5 | 83.93% | >=80% | PASS |
| Recall@10 | 87.50% | >=85% | PASS |
| MRR | 0.605952 | >=0.75 | FAIL |
| nDCG@10 | 0.671724 | >=0.80 | FAIL |
| Citation validity | 100.00% | >=98% | PASS |
| Citation coverage | 96.96% | >=95% | PASS |
| No-answer F1 | 100.00% | >=85% | PASS |
| Intent accuracy | 94.74% | >=95% | FAIL |
| Canonicalization | 94.74% | >=90% | PASS |
| Clarification precision/recall | 92.31% / 100.00% | >=85% / >=85% | PASS |
| Context merge | 100.00% | >=95% | PASS |
| 型号/告警幻觉 | 0 / 0 | 0 / 0 | PASS |
| Scope leakage | 0 | 0 | PASS |
| Error rate | 0.00% | 0% | PASS |

性能全部通过：Fast Path p95=1096.438 ms，Deterministic Understanding p95=1.552 ms，Multi-query p95=3551.384 ms，Full deterministic path p95=3467.506 ms。

## 10. Optional MiniMax Canary

- eligible/called：Canary component 记录 attempted=12；本执行中所有 eligible 调用均计入 attempted，因此 called=12。
- structured success=10/12（83.33%），fallback=2，p95=5013.361 ms。
- 失败后 deterministic preservation=100.00%；SLO=False。
- ambiguity accuracy 没有作为独立 Canary 字段发出，不能伪报；前置 Ambiguity Probe 的正确解释覆盖为 100.00%。
- quality gain：Candidate R@50=+0.000000，R@5=+0.000000，MRR=+0.000000，clarification P/R=+0.000000/+0.000000。结论：没有增益，也没有退化。
- 可选组件 structured 目标 >=95% 未通过（83.33%）；p95 <=5000ms 未通过（5013.361ms）。

## 11. Formal 测试

- deterministic-only Canary 未通过，所以没有创建、冻结或运行 `task25b_r3_dev_r5_r4_mm_zh_v1`。
- created=false；frozen=false；SHA-256=NOT CREATED；official run count=0；正式结果未用于调参。
- Formal 脚本仅实现前置门禁，未执行；API 显示 `NOT_CREATED_DETERMINISTIC_CANARY_FAILED`。

## 12. 向量只读对账

- Collection：`energy_kn_te_v4_1024_v1`；状态：`PASSED`；read-only=True。
- pilot_r2=1262；pilot_r3_semantic=416；pilot_r4_grounded=1289；pilot_r5_query_aware=2508。
- re-embedded/re-upserted=0/0；missing/orphan/duplicate/mismatch=0/0/0/0。
- 默认 Partition affected=False；Collection/Partition 未创建、删除或修改；正式全量重建未执行。

## 13. 完整回归

- compileall：`PASSED`（app/scripts/tests）。
- Alembic heads/current：`20260712_0013` / `20260712_0013`。
- pytest：249 passed，3 skipped，4 warnings，failed=0。
- Security：config `PASSED`；secret scan `PASSED_WITH_NOTES`（findings=9，blocking=0）；log `PASSED`；upload 11/11；RBAC 40/40。
- 业务流：DashVector hybrid 使用 fake-in-memory 且无真实向量写；multimodal evidence、multimodal agent、diagnosis/SOP/task agent、curator、artifact conversion 和 concurrency 全部通过。
- npm install `PASSED`；npm audit vulnerabilities=0；build `PASSED`；vue-tsc `PASSED`；static install `PASSED`，复制 60 个文件。

## 14. 前端、浏览器与 Final Smoke

- Retrieval Quality 页面已增加只读 R5-R4-MM 面板，展示 deterministic-first、MiniMax optional、Probe、Canary、Formal 和向量状态；后端受 RBAC 保护的 summary API 已返回最新状态。
- 真实浏览器审核：`NOT_EXECUTED_TOOL_BOOTSTRAP_BLOCKED`。所要求的应用内浏览器运行时初始化失败：`Cannot redefine property: process`。因此浏览器 gate 脚本未执行、未生成 browser evidence，console/page/network 三项不能声称为 0；没有伪造页面审核结论。
- Final Smoke：`PASSED`，base URL `http://127.0.0.1:8012`，23 checks，failed=0；默认跳过会新增 qa_records 的 retrieval write。

## 15. 边界与未执行项

- `backend/.env` SHA-256 与冻结值一致，changed=false；未打印 Key、Authorization、完整 prompt 或完整模型响应。
- engineering approval changed=false；expert_verified written=false；正式全量重建=false；默认 Partition 未修改。
- LoongArch + Kylin 未进行物理实机验收，不能声称通过。
- 未创建新 ZIP；既有 3 个 ZIP 的 hash/size 不变；delivery、delivery_staging 与 docs.zip 未更新。
- staged files=0；未执行 git add/commit/reset/clean/restore；保留全部现有工作区更改。

## 16. 最终判断

- deterministic RAG ready：**否**，iteration 2 仍有 4 个硬门失败。
- optional MiniMax usable：**仅可继续作为安全可降级的实验组件，当前未达到 Canary SLO**。
- graceful degradation：**通过，100% 无损**。
- Formal quality：**未评估，正式集未创建且 official run count=0**。
- allow Task 25C：**否**。
- remaining blockers：Candidate Recall@50、MRR、nDCG@10、intent accuracy，以及真实浏览器审核工具链阻塞。

## Machine evidence

机器证据位于 `.runtime/task25b_r3_dev_r5_r4_mm/`。本任务只生成本 Markdown 报告，不生成其他恢复报告。
