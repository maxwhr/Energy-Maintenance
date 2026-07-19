# Task 25B-R3-DEV-R5-R3-MM Query Understanding Contract Report

Result: `QUERY_UNDERSTANDING_CONTRACT_NOT_READY`

本轮完成了 Query Understanding v2 极简合同、确定性语义合并、确定性 Retrieval Planner v2、一次性同样本 MiniMax 模型 A/B、严格前置门禁和完整回归。两个候选模型均未同时达到结构化质量与 4 秒 p95 硬门，因此生产运行时保持 `deterministic`；版本化 Canary 未运行，正式测试集未创建，RAG 最终质量未通过。本结论是门禁正确阻断，不是系统崩溃或被测试跳过。

## 1. R5-R2-MM 失败基线

- 冻结结果：`QUERY_AWARE_GROUNDED_RAG_MM_QUALITY_GATE_FAILED`。
- Query Understanding：0/12 structured success，p95 16937.186 ms。
- Deterministic rerank：`PASSED`，Top1 95.00%。
- Optional Tie-break：75.00% structured success，p95 4441.677 ms。
- R5-R2-MM 主报告及 7 份关键机器证据共 8 项 SHA-256 均未变化；旧 runtime 和失败探针未覆盖。

## 2. 复杂 Schema 失败根因

旧合同将意图分类、口语标准化、明确实体、检索假设、Anchor、通道权重和嵌套 retrieval queries 混在一次模型调用中。嵌套对象、required 字段与输出长度共同放大 `NO_TOOL_USE`、字段缺失、Schema 校验失败和重试延迟；同时职责混合使模型输出可能影响检索事实边界。修复不是增加 timeout/max_tokens，而是拆分模型与系统职责。

## 3. Query Understanding v2 Schema

- 强制工具：`submit_query_understanding_v2`；`additionalProperties=false`。
- 平面字段仅 8 个：`intent`、`canonical_query`、`requested_information`、`ambiguity`、`missing_slots`、`needs_clarification`、`clarifying_question`、`confidence`。
- `canonical_query` 最长 256；requested information 最多 3 项；missing slots 最多 4 项；追问最长 160。
- 不含 retrieval queries/hypotheses、secondary intents、device models、alarm codes、Anchor、权重或维修答案。
- 12 条真实 Schema Probe：11/12 通过；nested retrieval query=0；唯一失败为一次 4 秒预算 timeout，状态 `FAILED`。

## 4. 系统侧语义合并

`QueryUnderstandingMergeService` 合并确定性信号、已验证 v2 patch、会话补充与完整性判断。型号、告警、数字和条件由系统确定性结果持有；模型不能覆盖或新增型号/告警；用户补充优先于历史推测；canonical query 若违反确认实体边界会被清理并回退。

- Context Merge：10/10，accuracy=100.00%，达到 >=95% 硬门。
- 缓存只保存 Pydantic 验证通过的 v2 patch；key 包含 provider/model/schema/prompt/query hash/confirmed signal hash/上下文澄清状态；错误与 fallback 不冒充模型成功。

## 5. 确定性 Retrieval Planner v2

- 仅由系统生成最多 4 条：ORIGINAL、CANONICAL、INTENT_QUERY、CONDITION_QUERY。
- ORIGINAL 始终保留；模型不再返回查询、Anchor 或权重。
- `COMMUNICATION` 映射 COMMUNICATION/SYMPTOM/CAUSE/ACTION/VERIFICATION；`PROCEDURE` 映射 PROCEDURE/ACTION/PREREQUISITE/SAFETY/VERIFICATION。
- 权重来自配置，检索假设标记为非事实，不使用 expected labels 或 case-id 特判。
- Planner Probe：20/20；ORIGINAL 保留 100.00%；最大查询数 4；型号/告警幻觉 0/0；状态 `PASSED`。

## 6. M3 与 M2.7-highspeed 同样本 A/B

两个模型使用同一 30 条 Train/Dev 样本、相同 v2 Schema、Anthropic forced tool choice 和 `service_tier=standard`，每个模型只完整运行一次。

| 指标 | MiniMax-M3 | MiniMax-M2.7-highspeed | 硬门 |
|---|---:|---:|---:|
| structured success | 22/30 (73.33%) | 0/30 (0.00%) | >=95% |
| tool-use success | 76.67% | 0.00% | 合同必要条件 |
| intent accuracy | 63.33% | 0.00% | >=95% |
| canonicalization | 63.33% | 0.00% | >=90% |
| clarification precision | 22.73% | 0.00% | >=85% |
| clarification recall | 71.43% | 0.00% | >=85% |
| hallucinated model/alarm | 0/1 | 0/0 | 0/0 |
| p50 | 3391.141 ms | 4506.640 ms | 记录项 |
| p95 | 4461.794 ms | 4513.682 ms | <=4,000 ms |
| provider errors/timeouts | 7/7 | 30/30 | error rate=0 |
| error rate | 26.67% | 100.00% | 0% |
| total tokens observed | 15508 | 0 | 记录项 |

M3 明确发送 thinking disabled；M2.7-highspeed 按 Provider 能力不伪造关闭。MiniMax 官方 Anthropic 文档说明 M2.x thinking 不可关闭；官方模型说明将 M2.7-highspeed 定位为相同能力的高速版本：[Anthropic API](https://platform.minimaxi.com/docs/api-reference/text-chat-anthropic)，[Models overview](https://platform.minimax.io/docs/guides/models-intro)。本轮未记录 thinking 内容、完整 prompt、完整响应或 Authorization。

## 7. 最终运行时模型选择

- 选择：`deterministic`。
- 原因：`neither candidate model passed every structured-quality and latency gate`。
- MiniMax-M3 未达到 structured、intent、canonicalization、clarification、零告警幻觉、p95 和 error-rate 门。
- MiniMax-M2.7-highspeed 在任务 4 秒总预算下 30/30 timeout，未达到任何模型主路径门。
- 两者均失败时按任务规定保持 deterministic normalization，未修改 `backend/.env` 的主模型配置。

## 8. 延迟、请求与重试边界

- Query Understanding 默认一次请求；普通 4xx、NO_TOOL_USE、字段缺失、未知枚举和 Schema failure 不重试。
- 仅 connection reset/refused、请求未送达、明确 502/503 可在总预算内快速重试一次。
- 总预算 4 秒，超预算立即 deterministic fallback，不允许放大到 10–20 秒。
- 探针模式完整记录错误但不因 Schema failure 开 breaker；生产 breaker 仅统计 timeout、5xx、传输错误与连续 NO_TOOL_USE；Query/Tie-break 独立。
- Schema validation failure 单独计数，M3 A/B 后 Query breaker 仍为 `CLOSED`。

## 9. Tie-break

- `DeterministicEvidenceRerankService` 保持启用。
- MiniMax Tie-break 生产默认关闭，仅能通过实验/管理员显式配置开启；失败保持确定性顺序。
- Tie-break 不参与本轮 Query Understanding 前置门，也未阻断合同判定。

## 10. Contract Gate

- 状态：`QUERY_UNDERSTANDING_CONTRACT_NOT_READY`；ready=False。
- 通过项：context merge、planner、deterministic rerank、零型号幻觉、零告警幻觉门的综合安全判断。
- 阻断项：runtime_model_selected, structured_success, p95_ms, intent_accuracy, canonicalization_accuracy。
- 95% structured success：**未满足**。
- 4 秒 p95：**未满足**。

## 11. Canary

- 数据集名称保留为 `task25b_r3_dev_r5_r3_mm_train_dev_v1`，但未创建/执行 60 条版本化 Canary 数据。
- 状态：`QUERY_UNDERSTANDING_CONTRACT_NOT_READY`；executed cases=0；iterations=0。
- 没有运行 iteration 2，没有执行 Train/Dev 校准，没有降低门槛。

## 12. 正式测试

- 因前置合同失败，`task25b_r3_dev_r5_r3_mm_zh_v1` 未创建、未冻结、未运行。
- 正式 run count=0；正式结果未用于调参；正式质量门未运行。

## 13. 向量只读对账

- Collection：`energy_kn_te_v4_1024_v1`；状态 `PASSED`；read-only=True。
- partition：pilot_r2=1262，pilot_r3_semantic=416，pilot_r4_grounded=1289，pilot_r5_query_aware=2508。
- re-embedded/re-upserted=0/0。
- missing/orphan/duplicate/mismatch=0/0/0/0。
- Collection/Partition 创建删除=0；默认 Partition 修改=False；正式全量重建未执行。

## 14. 完整回归

- compileall：`PASSED`。
- Alembic heads/current：`20260712_0013 (head)` / `20260712_0013 (head)`。
- pytest：227 passed，3 skipped，4 warnings；普通 pytest 未调用真实外部 API。
- 定向 tests：unit `10/10 PASSED`；integration `5/5 PASSED`。
- Security：config `PASSED`；secret scan `PASSED_WITH_NOTES`，blocking=0；log `PASSED`；upload `PASSED_11_OF_11_ISOLATED_TEST_SCHEMA`。
- 上传安全在独立 PostgreSQL test schema 运行 11/11 后删除 schema 和隔离文件，生产知识文档增加 0。
- RBAC：40/40；业务回归：DashVector hybrid `PASSED_FAKE_IN_MEMORY`，其余 multimodal/agents/curator/artifact/concurrency 均通过，真实 DashVector called=False。
- 前端：npm install `PASSED`，audit vulnerabilities=0，build `PASSED`，vue-tsc `PASSED`，static `PASSED_60_FILES`。

## 15. 浏览器与 Final Smoke

- 浏览器：`PASSED`；质量页展示 v2 11/12、M3/M2.7-HS 同样本结果、deterministic 运行时、Canary 0、Formal 未创建和向量只读不变。
- 口语通信查询实际显示“确定性标准化（无外部调用）”、4 条确定性查询和原始手册引用。
- R5-R3 面板 mutation buttons=0；RBAC 独立验证 viewer 边界；console/page/unexpected network errors=0/0/0；未渲染 Key 或 token 值。
- Final Smoke：23/23 passed，failed=0；默认跳过会新增 qa_records 的 retrieval write。

## 16. backend/.env 未修改

- 任务前后 SHA-256 一致：`True`。
- 未修改 `backend/.env`，未在命令、报告、runtime、浏览器或日志输出 API Key。

## 17. 正式全量重建与审核边界

- `TASK25B_ALLOW_FULL_REINDEX=false`；正式全量重建、Embedding 再生成、真实向量 upsert 均未执行。
- engineering approval 未修改；`expert_verified=false`，未写专家审核结果。
- 未增加知识文档或 Semantic Unit；fake 业务回归产生的 3 个临时知识夹具已精确清除。

## 18. 未打包、未提交 Git

- 未创建 ZIP；任务开始时已有 3 个 ZIP，hash 全部不变。
- 未执行 git add/commit/reset/clean/restore；staged count=0；`git diff --check` 通过。
- 未执行工作区清理，用户已有脏工作区和无关改动均保留。

## Final judgment

- selected model：`deterministic`。
- why：M3 与 M2.7-highspeed 都没有满足全部模型硬门。
- same-sample result：M3=22/30 structured、p95 4461.794 ms；M2.7-highspeed=0/30 structured、p95 4513.682 ms。
- 95% structured gate：未满足。
- 4-second p95 gate：未满足。
- Canary executed：否，0 cases。
- Formal executed：否，run count 0。
- RAG final quality passed：否。
- final status：`QUERY_UNDERSTANDING_CONTRACT_NOT_READY`。

## Machine evidence

本任务机器证据统一位于 `.runtime/task25b_r3_dev_r5_r3_mm/`。本轮只生成本报告，不生成其他任务 Markdown 报告。
