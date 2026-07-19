# Task 25B-R3-DEV-R5-R2-MM MiniMax Query-Aware RAG Report

Result: `QUERY_AWARE_GROUNDED_RAG_MM_QUALITY_GATE_FAILED`

MiniMax-M3 的模型列表、Anthropic 兼容端点和强制 Tool Calling 探针通过；确定性证据重排也通过定向质量门。但是核心 Query Understanding 的真实 Tool Calling 结构化成功率为 **0/12**，p95 为 **16937.186 ms**，未达到 >=95% 和 <=4,000 ms 的硬门。因此两个 Canary 入口均被前置门禁阻断，正式数据集未创建、正式测试未运行。本结果是明确的质量门禁失败，不是完整通过。

## 1. R5-R1 冻结基线

- 冻结结果：`QUERY_AWARE_GROUNDED_RAG_R1_QUALITY_GATE_FAILED`；R5-R1 Canary：`BLOCKED_PRECANARY`。
- Structured / StepFun Rerank / RAW_VECTOR：`PASSED` / `FAILED` / `PASSED`。
- 冻结 pytest：189 passed，3 skipped；Alembic heads/current 均为 `20260712_0013 (head)`。
- R5-R1 主报告及 8 份关键机器证据的 SHA-256 复核全部未变。
- `.runtime/task25b_r3_dev_r5/` 与 `.runtime/task25b_r3_dev_r5_r1/` 未被覆盖。

## 2. MiniMax-M3 模型可用性

- 模型列表访问：`True`；`MiniMax-M3` 可用：`True`。
- Anthropic 兼容端点：`True`；协议：`anthropic`；模型：`MiniMax-M3`。
- 探针状态：`PASSED`；延迟：3164.844 ms；服务等级：`standard`。
- 实现直接复用 `httpx.AsyncClient` 长连接池，没有增加 Anthropic SDK 或重量级依赖。
- 协议实现参考 MiniMax 官方 [Anthropic API 文档](https://platform.minimax.io/docs/api-reference/text-anthropic-api) 与 [文本生成指南](https://platform.minimaxi.com/docs/guides/text-generation)。

## 3. Anthropic Tool Calling

- 极简强制工具调用收到 `tool_use`：`True`；输入通过 Pydantic：`True`。
- `tool_choice` 使用指定工具名；`thinking` 固定为 disabled；`service_tier` 固定为 standard。
- Adapter 识别 text/tool_use/thinking 内容块，但不记录 thinking 内容、完整 tool input、完整响应或 Authorization。
- 意外 text/thinking block：`False` / `False`；thinking 内容写日志：`False`。

## 4. Thinking disabled

- 配置与请求均为 `{"type":"disabled"}`。
- 真实探针未发现 thinking block，日志脱敏检查通过。
- 前端仅显示布尔状态，不显示隐藏推理。

## 5. Query Understanding

- 总样本：20；计划 MiniMax Tool / Fast Path / Deterministic Normalization：12 / 4 / 4。
- 实际模式：Fast Path `4`，Deterministic Normalization `4`，MiniMax Tool `0`，Safe Fallback `12`。
- MiniMax structured success：`0/12`（0.0%）；10 次真实外部尝试后熔断，余下 2 条安全短路。
- 失败类型包括 3 个 `NO_TOOL_USE`、1 个 timeout，以及缺少 required 字段/检索查询子字段。诊断探针状态：`DIAGNOSTIC_ONLY`。
- Confirmed facts 保持：100.0%；normalized semantics 非空：95.0%；hypotheses 隔离：100.0%。
- 型号/告警幻觉：0 / 0。
- p50/p95：4676.538 ms / 16937.186 ms；核心性能门失败。
- 意图准确率和 canonicalization accuracy 未在 Canary 计分，不能宣称通过。

## 6. Deterministic Rerank

- 状态：`PASSED`；样本/候选：20 / 44。
- 权重版本：`task25b_r3_dev_r5_r2_mm_v1`；权重总和：1.0。
- Top1：95.0%；候选边界/来源保持：100.0% / 100.0%。
- Exact model / exact alarm + valid citation 保护：通过；无型号查询不产生型号偏置：`True`。
- 真正实体/告警冲突和重复使用独立可解释 penalty；多文档互补证据不会仅因来源不同而被惩罚。
- p50/p95：0.075 ms / 1.677 ms。
- Recall@5 和 MRR 前后值未运行 Canary，因此为 `NOT RUN`。

## 7. MiniMax Tie-break

- 状态：`OPTIONAL_MINIMAX_TIEBREAK_DEGRADED`；eligible/called：20/20。
- Structured success：15/20（75.0%），未达到 95% 组件 SLO。
- 候选新增/移除/来源修改：0/0/0。
- 模拟失败时原确定性顺序保持：100.0%。
- p50/p95：3175.320 ms / 4441.677 ms；延迟门通过，但结构化成功率门失败。
- Tie-break 是可选组件；失败时不改变候选、来源、Citation、确定性顺序或请求可用性。

## 8. Provider A/B

- 状态：`RECORDED_FROM_REAL_PROBES_QUERY_GATE_FAILED`；同样本 A/B：`False`。
- MiniMax Query：0/12，p95 16937.186 ms；MiniMax Tie-break：15/20，p95 4441.677 ms。
- 冻结 StepFun Query directed probe：4/4（非同样本）；冻结 StepFun Rerank：0/3，历史 p95 约 19.9 s。
- Query gate 失败后没有继续制造同请求 Provider 链；`request_level_chaining=false`。
- 当前选择：Query 使用 deterministic safe fallback；主重排使用 deterministic evidence rerank；MiniMax 仅为 degraded optional tie-break。

## 9. Provider 熔断

- Query Understanding breaker：`OPEN`；Tie-break breaker：`CLOSED`。
- 独立统计 timeout、结构化失败窗口和连续 5xx，并支持 half-open probe。
- Query/Tie-break 使用独立 TTL/LRU cache key 与独立 breaker，避免一个组件拖垮另一个组件。

## 10. 无损降级

- MiniMax 未配置、熔断、超时、无目标 tool_use 或 Schema 校验失败时回退 deterministic normalization。
- 请求内不串行等待 StepFun；远程模型不构成单点故障。
- Tie-break 失败顺序保持率 100%；候选、来源、Citation 无增删改。
- 浏览器实测了 Fast Path 和 MiniMax 被运行时门禁关闭时的 safe fallback，两者均返回可观察状态和真实引用。

## 11. Canary

- Iteration 1 / 2：`NOT_RUN_PRECONDITION_FAILED` / `NOT_RUN_PRECONDITION_FAILED`。
- 汇总：`CANARY_NOT_RUN_QUERY_GATE_FAILED`；真实执行样本：0；真实迭代：0。
- 阻断：`QUERY_UNDERSTANDING_PROBE_FAILED`。没有用空结果伪装 Canary，也没有降低门槛或调参。

## 12. 正式测试

- 数据集：`None`；创建状态：`NOT_CREATED_CANARY_FAILED_OR_NOT_RUN`；冻结：`False`。
- 正式质量门：`NOT_RUN_CANARY_FAILED_OR_NOT_RUN`；run count：0。
- 因 Canary 未通过，正式集未创建、未冻结、未运行。

## 13. 性能

- Fast Path p50/p95：0.115 ms / 0.125 ms。
- Query Understanding p50/p95：4676.538 ms / 16937.186 ms。
- Deterministic Rerank p50/p95：0.075 ms / 1.677 ms。
- Optional Tie-break p50/p95：3175.320 ms / 4441.677 ms。
- Multi-query / Deep Path：`NOT RUN`（Canary 被核心组件门禁阻断）。
- Query timeout：1；Tie-break timeout：0。Cache 契约测试通过，真实 cache hit rate 未单独计量。

## 14. Citation

- Deterministic probe 的候选边界和来源保持均为 100%；Tie-break 来源修改为 0。
- Query-Aware 链在最终 refinement 后重新校验 Scope 与 Citation；缓存结果也必须重新校验。
- 浏览器 Fast Path 与 Safe Fallback 均显示真实 Citation。
- Canary 未运行，Citation validity/coverage 正式数值为 `NOT RUN`，不能沿用旧基线宣称本版本通过。

## 15. No-answer

- 无证据时仍保持 grounded answer boundary，不把 retrieval hypothesis 当作确认事实或 Citation。
- Canary 未运行，因此本版本 No-answer precision/recall/F1 为 `NOT RUN`。

## 16. 向量只读对账

- Collection：`energy_kn_te_v4_1024_v1`；状态：`PASSED`；read-only：`True`。
- 分区：pilot_r2=1262，pilot_r3_semantic=416，pilot_r4_grounded=1289，pilot_r5_query_aware=2508。
- re-embedded/re-upserted：0/0。
- missing/orphan/duplicate/mismatch：0/0/0/0。
- 默认 Partition 修改：`False`。

## 17. 回归

- compileall：`PASSED`。
- Alembic heads/current：`20260712_0013 (head)` / `20260712_0013 (head)`。
- pytest：212 passed，3 skipped，4 warnings；普通 pytest 未调用真实外部模型。
- 定向 tests：unit 16/16，integration 7/7。
- Security：config `PASSED`，secret scan `PASSED_WITH_NOTES`（blocking 0），log sanitization `PASSED`，upload `PASSED`。
- RBAC：40/40 passed。
- Agents/Conversion：multimodal、diagnosis/SOP/task、curator、artifact conversion、conversion concurrency 均通过；DashVector 回归使用 fake in-memory，未调用真实 DashVector。
- Frontend：npm audit 0 vulnerabilities，build `PASSED`，vue-tsc `PASSED`，static install `PASSED`。

## 18. 浏览器

- 状态：`PASSED`；URL：`http://127.0.0.1:8012/system/retrieval-quality`。
- R5-R1 冻结基线、MiniMax 模型/Tool、Query failure、Deterministic pass、Tie-break degraded、breakers、Canary/Formal gate、向量未修改均可见。
- Fast Path、safe fallback、确定性重排和 Citation 均通过真实页面交互验证。
- Viewer 只读边界：通过；console/page/unexpected network errors：0/0/0；未渲染 Key 或 Authorization。

## 19. Final Smoke

- `http://127.0.0.1:8012`：23/23 passed，failed=0。
- 为避免新增 qa_records，smoke 按默认策略跳过写入型 retrieval query；浏览器查询感知链路已单独验收。

## 20. backend/.env 未修改

- 任务前后 SHA-256 完全一致：`True`。
- 报告、runtime JSON、浏览器和日志均不含 API Key、Authorization、完整 Prompt 或完整模型响应。

## 21. expert_verified=false

- 未写 expert verification，未修改 engineering approval，未伪造专家审核。

## 22. 正式全量重建未执行

- 未执行知识全量重建、Embedding 重生成、向量 upsert、Collection/Partition 创建或删除。
- `TASK25B_ALLOW_FULL_REINDEX` 在真实任务进程中保持 false。

## 23. 默认 Partition 未修改

- 四个既有 Pilot 分区计数与冻结快照一致；default partition affected=false。

## 24. LoongArch

- 未在真实 LoongArch + Kylin 机器执行。
- 未引入 CUDA/GPU、本地大模型、FAISS、pgvector、Neo4j、Docker 或重量级 SDK。

## 25. 未打包

- 未创建 ZIP；冻结时已有 3 个 ZIP 的 SHA-256、大小保持不变。
- `delivery`、`delivery_staging` 和 `docs.zip` 未更新。

## 26. 未提交 Git

- 未执行 git add/commit/reset/clean/restore；staged count=0。
- 任务开始前的脏工作区及用户已有改动被保留。

## Final judgment

- Final result：`QUERY_AWARE_GROUNDED_RAG_MM_QUALITY_GATE_FAILED`。
- MiniMax 适用性：模型端点和极简 Tool Calling 可用，但当前复杂 Query Understanding Schema 不适合进入质量通过状态。
- 口语支持：系统能够安全降级，MiniMax 口语理解质量尚未证明。
- Deterministic ranking competitive：定向 Top1 95%、边界/来源 100%，但 Canary Recall/MRR 未运行，端到端竞争力未证明。
- Optional Tie-break：可安全使用为降级可选组件，当前 75% structured success 未达 SLO。
- Graceful degradation：通过。
- RAG quality competitive：未证明。
- Allow Task 25C：否。
- Remaining blockers：将 Query Understanding Tool structured success 提升至 >=95%，p95 降至 <=4,000 ms；随后运行版本化 Canary。只有 Canary 通过才允许创建和运行一次正式测试。

## Machine evidence

本任务机器证据统一位于 `.runtime/task25b_r3_dev_r5_r2_mm/`。只生成本报告，不生成模块级独立 Markdown 报告。
