# Task 25B-R3-DEV-R5-R5 候选召回与确定性排序专项报告

最终状态：`QUERY_AWARE_GROUNDED_RAG_R5_QUALITY_GATE_FAILED`

结论：候选召回已达到硬门（Candidate Recall@50=0.950000），但直接答案 Hit@1/Hit@3、Recall@5/Recall@10、MRR、nDCG@10、canonicalization 及多查询/全链路延迟仍未达标。因此正式盲测未创建、未冻结、未运行，当前不允许进入 Task 25C。

## 1. R5-R4-MM 冻结基线

- 基线状态：`QUERY_AWARE_GROUNDED_RAG_R4_QUALITY_GATE_FAILED`；iteration 1/2 每配置案例数分别为 81 / 76，历史不一致已保留为证据。
- 基线 iteration 2：Candidate R@50=0.910714，R@5=0.839286，R@10=0.875000，MRR=0.605952，nDCG@10=0.671724。
- 13 个 R5-R4-MM 受保护产物、3 个既有 ZIP、`.env` SHA-256 和 staged=0 均已冻结；旧运行目录未改写。

## 2. 固定 Train/Dev 数据集与 Evaluation Evidence Identity

- 版本：`task25b_r3_dev_r5_r5_train_dev_v1`；案例数：80。
- dataset SHA-256：`da21c4b9988340d5b6f9df1f1478bff2780a41bf752529d745627ea255e8f0e5`。
- label SHA-256：`0ed9bd1c549ee9728b53f35882106daa6dee1ea0ed1347f35a06dc29f2f61200`。
- iteration 1 / 2 均为 80 条，dataset/label hash 完全相同，变更数 0。
- 覆盖：复合意图 39、no-answer 8、需追问 12、HTML FAQ 7、PDF 53、多文档互补 20。
- `EvaluationEvidenceIdentity` 明确 CHUNK / SEMANTIC_UNIT / SECTION / DOCUMENT 层级、direct/supporting/background 证据和 3/2/1/0 分级相关性；Semantic Unit 到 source chunks 的映射参与命中判断，禁止整文档或整章节无条件扩展为 relevant。

## 3. Candidate miss 逐案例取证

- 总计 17 个旧基线 miss，全部有唯一主要原因，UNKNOWN=0。
- 分布：EVALUATION_IDENTITY_MISMATCH=12，ANCHOR_TYPE_TOO_NARROW=4，PLANNER_QUERY_MISSING=1；其余查询归一化、复合意图、keyword、raw vector、semantic、channel budget/aggregation、RRF、source mapping、refinement、true corpus gap、label error 均为 0。
- 结论：12 个是评估身份/追问边界分母不匹配，4 个是快速关键字路径 Anchor 过窄，1 个缺少 Planner 查询；没有把问题统一归为 UNKNOWN，也没有扩大 expected IDs。

## 4. Ranking error 逐案例取证

- 排序错误 15 个：Top50 未进 Top5=4，Top5 未进 Top2=11。
- 分布：RELEVANCE_GRADE_NOT_USED=9，GENERIC_SECTION_OVER_SPECIFIC=4，INSUFFICIENT_REQUESTED_INFO_COVERAGE=1，WRONG_ALARM=1。
- 已记录各阶段 rank、意图/信息覆盖、实体/条件、来源特异度、RRF/rerank breakdown 和错误 Top1 原因。

## 5. Composite Intent 与 requested_information

- 旧基线 intent 错误 4 个，全部为 `TRIGGER_PRECEDENCE`；旧准确率 0.947368。
- 新合同区分 `primary_intent` 与最多 5 个 `requested_information`，复合案例 39 个；未按 case_id 写规则。
- iteration 2：primary intent accuracy=0.950000；requested information P/R/F1=0.960630/0.884058/0.920755；primary intent 错误 4 个；型号/告警幻觉=0/0。

## 6. Planner V3、Anchor Coverage Matrix 与候选预算

- 平均查询变体 4.119；原始查询保留 67/67；最多 5 条（ORIGINAL/CANONICAL/SYMPTOM_QUERY/REQUEST_QUERY/CONDITION_QUERY）。
- Anchor matrix：`task25b_r3_dev_r5_r5_anchor_matrix_v1`；requested information 的 Anchor 类型取并集，`FULL_SECTION` 仅为低权重辅助召回。
- 预算：EXACT_KEYWORD=30，SCOPED_KEYWORD=80，RAW_VECTOR=80，SEMANTIC_UNIT=100；通道内 identity 上限 60，融合上限 150，Candidate 指标严格按 Top50。

## 7. Evidence Identity、RRF、Deterministic Rerank V2 与 refinement

- 候选以 Semantic Unit、明确 Section 或 Chunk 构造稳定 evidence identity，同源证据跨通道合并。
- Deterministic Rerank V2 使用 direct answer、requested information coverage、实体/条件、来源特异度和泛化惩罚；本轮唯一校准版本：`task25b_r3_dev_r5_r5_deterministic_rerank_v2_calibrated_1`。
- surfaced candidates 中触发泛化惩罚 33 次；refinement 未解释相关证据丢失=0。
- 未启用新的 LLM tie-break，MiniMax 不作为本轮排序器。

## 8. Canary iteration 1 与唯一校准

| 指标 | iteration 1 | iteration 2 | 硬门 |
|---|---:|---:|---:|
| Candidate Recall@50 | 0.950000 | 0.950000 | >=0.95 |
| Recall@5 | 0.350000 | 0.533333 | >=0.80 |
| Recall@10 | 0.516667 | 0.600000 | >=0.85 |
| MRR | 0.287011 | 0.336806 | >=0.75 |
| nDCG@10 | 0.310396 | 0.363672 | >=0.80 |
| Direct Answer Hit@1 | 0.216667 | 0.200000 | >=0.70 |
| Direct Answer Hit@3 | 0.300000 | 0.450000 | >=0.85 |
| Requested Info Coverage@3 | 0.904444 | 0.939722 | >=0.90 |

- iteration 1 失败后仅执行一次校准；标签变更=false，删除案例=0，Formal 数据使用=false，知识增加=false，向量修改=false。
- 校准仅覆盖通用 trigger precedence、requested information 规则、semantic query 数量和 deterministic rerank 权重/排序优先级；未执行第三轮 Canary。

## 9. Canary iteration 2 最终门禁

- 状态：`QUERY_AWARE_GROUNDED_RAG_R5_QUALITY_GATE_FAILED`；失败门：`recall_at_5, recall_at_10, mrr, ndcg_at_10, canonicalization, direct_answer_hit_at_1, direct_answer_hit_at_3, multi_query_p95, full_deterministic_path_p95`。
- Citation validity/coverage=0.981667/0.981667；No-answer P/R/F1=1.000000/1.000000/1.000000。
- Clarification P/R=0.923077/1.000000；context merge=1.000000；scope leakage/error=0/0.000000。
- p95：Fast=1145.454ms，Understanding=0.828ms，Multi-query=5733.157ms，Full=8015.325ms。Multi-query 与 Full 超门。

## 10. Formal 测试

- created=false，frozen=false，dataset/SHA-256=null，run count=0，result=`NOT_EXECUTED_CANARY_FAILED`。
- Canary 未全通过，因此没有创建 `task25b_r3_dev_r5_r5_zh_v1`，没有调用 Formal runner，也没有使用 Formal 结果调参。

## 11. 向量只读对账

- Collection：`energy_kn_te_v4_1024_v1`；pilot_r2=1262，pilot_r3_semantic=416，pilot_r4_grounded=1289，pilot_r5_query_aware=2508。
- re-embedded/re-upserted=0/0；missing/orphan/duplicate/mismatch=0/0/0/0。
- default Partition affected=false；`.env` changed=false；staged files=0。

## 12. 完整回归

- compileall：PASSED（app/scripts/tests）。
- Alembic heads/current：`20260712_0013 (head)` / `20260712_0013 (head)`。
- pytest：270 passed，3 skipped，4 warnings，0 failed。
- 安全：config passed_with_warnings；secret scan passed_with_notes（9 notes，0 blocking）；log sanitization passed；upload security 11/11；RBAC 40/40。
- 业务与 Agent：DashVector hybrid（fake-in-memory、无真实向量写）、multimodal evidence、multimodal agent、diagnosis/SOP/task agent、knowledge curator、artifact conversion、conversion concurrency 全部通过。
- npm install/build/vue-tsc：PASSED；npm audit：0 vulnerabilities；静态安装：60 files。
- 真实 Playwright：26/26 PASSED，console/page/unexpected network errors=0/0/0，viewer 只读通过。
- Final smoke：23/23 PASSED，failed=0，Base URL=`http://127.0.0.1:8012`，确认 8012 为本轮代码。

## 13. 浏览器审核覆盖

- 已在真实 Chrome + 项目 Node/Playwright 中验证 primary intent、requested information、composite intent、canonical query、query variants、Anchor coverage、direct answer ranking、多证据排序、Citation、Confidence 与 no-answer boundary。
- viewer 可读取 Retrieval Quality 页面，R5 面板写控件数为 0；未渲染密码、Authorization 或 token。

## 14. 边界

- `backend/.env` hash 未变化；审批状态未修改；`expert_verified` 未写入。
- 未执行正式全量重建；`TASK25B_ALLOW_FULL_REINDEX=false`；默认 Partition 未修改。
- 未增加知识、Semantic Unit 或向量；未创建/删除 Collection/Partition。
- LoongArch + Kylin 物理实机验收未执行，不宣称通过。
- 未打包、未生成新 ZIP、未执行 Git add/commit/reset/clean/restore；staged=0。

## 15. 最终判断

- Candidate recall competitive：**是，刚好达到 0.95 硬门**。
- Direct evidence ranking competitive：**否**（Hit@1=0.20，Hit@3=0.45，MRR=0.336806，nDCG@10=0.363672）。
- Deterministic RAG ready：**否**。
- Formal quality：**未评估，Canary 阻断**。
- Allow Task 25C：**否**。
- Remaining blockers：Direct Answer Hit@1/3、Recall@5/10、MRR、nDCG@10、canonicalization、Multi-query p95 与 Full deterministic path p95。

## Machine evidence

机器证据位于 `.runtime/task25b_r3_dev_r5_r5/`。本任务只生成这一份 Markdown 报告。
