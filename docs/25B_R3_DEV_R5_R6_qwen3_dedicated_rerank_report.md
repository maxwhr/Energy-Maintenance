# Task 25B-R3-DEV-R5-R6：Qwen3 专用重排报告

## 结论

最终状态：`QWEN3_RERANK_CONFIG_MISSING`。

Qwen3 专用重排链路、硬实体/范围前置保护、确定性后置约束、缓存、熔断、失败降级、诊断接口及前端只读展示均已实现并通过本地与浏览器回归。但当前运行环境缺少精确的 DashScope Workspace Base URL，且专用重排开关保持关闭，因此真实 Qwen3 Probe 在配置门禁处停止：20 个 Probe 用例已选定，实际执行 0 个，未调用真实 Qwen3 API。按照任务的强制执行顺序，本轮没有创建新 Train/Dev、没有运行 Canary，也没有创建或运行 Formal 测试；不能宣称 Qwen3 排序增益或 R6 质量门通过。

## 1. R5-R5 基线

- 数据集版本：`task25b_r3_dev_r5_r5_train_dev_v1`，80 条固定 Train/Dev。
- 数据集 canonical hash：`da21c4b9988340d5b6f9df1f1478bff2780a41bf752529d745627ea255e8f0e5`。
- 标签 canonical hash：`0ed9bd1c549ee9728b53f35882106daa6dee1ea0ed1347f35a06dc29f2f61200`。
- Candidate Recall@50：0.950000。
- Recall@5 / Recall@10：0.533333 / 0.600000。
- MRR / nDCG@10：0.336806 / 0.363672。
- Direct Answer Hit@1 / @3：0.200000 / 0.450000。
- Requested Information Coverage@3：0.939722。
- Citation validity / coverage：0.981667 / 0.981667。
- No-answer F1：1.000000。

冻结校验在任务结束时再次通过：R5-R5 受保护工件 hash 未变化、旧 ZIP inventory 未变化、暂存文件为 0。

## 2. 为什么引入专用 Rerank

R5-R5 的 Candidate Recall@50 已达到 0.95，主要缺口不再是候选召回，而是第二阶段排序：直接回答常被泛化背景压制，且存在相似型号、相似告警及 requested information 覆盖不足。R6 因此使用专用 `qwen3-rerank` 判断候选是否直接回答问题；确定性规则只保留实体、范围、安全和覆盖硬约束，不再依靠大量手写权重承担完整语义排序。

正式链路为：Query Understanding → Retrieval Planner → Multi-query Retrieval → RRF → Hard Entity/Scope Guard → Qwen3 Dedicated Rerank → Deterministic Post-Rerank Guard → Refinement → Citation Validation → Confidence → Answer Boundary。MiniMax 仅保留为可选歧义消解器，不参与本轮排序主链路。

## 3. 配置和模型

- Provider：`dashscope`；模型：`qwen3-rerank`；接口路径：`/reranks`。
- 默认候选上限 / top_n：40 / 40，合法配置范围 20–50。
- connect/read/write/pool timeout、连接池和 Keep-Alive 由长生命周期 `httpx.AsyncClient` 管理。
- 当前 API Key 存在性检查通过，但 Workspace Base URL 不存在；没有猜测 WorkspaceId，也没有回退到其他工作空间或 Provider。
- Key、Authorization、Base URL 值及完整 Provider 响应均未写入报告或普通日志。

## 4. Rerank Text 设计

每个候选只使用 source-grounded 字段构造确定性文本：文档类型、产品族、设备型号、告警代码与名称、章节、语义单元类型、故障现象、可能原因、处理步骤、操作前提、完成验证、安全要求和来源短摘录。requested information 对应字段、直接证据和实体字段优先，背景段落降权；最长 1,500 字符。若源证据本身较短，不为凑足 800 字符而编造内容。Benchmark relevance grade、expected IDs、目标标题和正确答案均不进入请求。诊断仅记录 candidate ID、文本 hash 和长度，正式 Citation 仍指向原始证据。

## 5. Instruct 版本

版本：`task25b_r3_dev_r5_r6_instruct_v1`。

> Given an equipment maintenance troubleshooting query, rank passages that directly answer the user's requested information. Prefer specific, source-grounded causes, actions, procedures, prerequisites, safety requirements, and verification steps over generic background or merely topically related text. Penalize passages with mismatched device models, alarm codes, components, or occurrence conditions.

Instruct 不包含 case ID、expected IDs 或具体测试答案；本轮没有在迭代中临时变更版本。

## 6. Probe

- 计划用例：20；已执行：0；真实 API 调用：`false`。
- 12 类必需覆盖全部就绪：泛化章节/具体步骤、背景/直接答案、正确/相似型号、正确/相似告警、原因、动作、安全、前提、验证、HTML FAQ、PDF 手册、多相关证据。
- 结果：`QWEN3_RERANK_CONFIG_MISSING`。

配置门禁先于 Provider 请求生效，因此没有伪造 API 成功率、排序指标或延迟。Probe 文件中的 0.0 成功率仅表示 0/20 已执行，不代表 Qwen3 服务质量。

## 7. Deterministic 与 Qwen3 A/B

RRF、R5-R5 Deterministic Rerank V2、Qwen3、Qwen3 + Post Constraints 四路比较结构已实现，但因真实 Probe 未执行，只有确定性基线可报告。Qwen3 A/B：未测量；不能声称优于或不劣于基线。

## 8. Direct Answer Hit

- Deterministic 基线 Hit@1：0.200000。
- Deterministic 基线 Hit@3：0.450000。
- Qwen3 / Qwen3 + Post Constraints：未测量，原因是 `QWEN3_RERANK_CONFIG_MISSING`。

## 9. Recall、MRR 与 nDCG

| 配置 | Candidate Recall@50 | Recall@5 | Recall@10 | MRR | nDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| R5-R5 Deterministic | 0.950000 | 0.533333 | 0.600000 | 0.336806 | 0.363672 |
| Qwen3 | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 |
| Qwen3 + Post Constraints | 未测量 | 未测量 | 未测量 | 未测量 | 未测量 |

## 10. Provider 成功率

真实请求数为 0，Provider 成功率未测量。适配器对 index 越界、重复 index、空结果、无效 JSON、超时、429、5xx 和模型不可用均返回脱敏 reason code，不依赖 Provider 返回的 document 正文。

## 11. 延迟

真实 Provider 延迟和 Qwen3 component p95 未测量。查询响应仍输出独立阶段延迟；由于配置门禁在网络请求前生效，本地降级路径没有把“未调用”误报为 Qwen3 延迟结果。

## 12. 降级和熔断

- 配置缺失或 Provider 失败时，候选顺序精确保留 R5-R5 确定性结果；候选、正文、来源和 Citation 均不变。
- 失败路径不会串行调用 MiniMax 或 StepFun；后置重排约束也会跳过，以免改变确定性 fallback 顺序。
- 只有成功结果进入 TTL/LRU 缓存；Provider 错误与 fallback 不按成功缓存。
- 熔断器独立维护失败阈值和冷却时间；当前状态 `CLOSED`。
- final smoke 已验证 fallback reason 为 `QWEN3_RERANK_CONFIG_MISSING`、fallback order preserved=true、candidate additions/source modifications=0。

## 13. Canary

未运行。Probe 没有通过配置和增益门禁，因此没有越级创建 R6 Train/Dev，也没有生成 Canary iteration 1/2、case results、comparison 或 latency 工件。状态：`NOT_RUN_AFTER_PROBE_GATE`，不冒充 `QUERY_AWARE_GROUNDED_RAG_R6_QUALITY_GATE_FAILED`，因为质量测量尚未发生。

## 14. Formal

未创建、未冻结、未运行。Canary 未通过前禁止生成至少 100 条的独立 Formal 数据集，因此 Formal run count=0；没有依据正式结果调参。

## 15. 向量只读对账

| Partition | 冻结值 | 结束值 |
| --- | ---: | ---: |
| pilot_r2 | 1,262 | 1,262 |
| pilot_r3_semantic | 416 | 416 |
| pilot_r4_grounded | 1,289 | 1,289 |
| pilot_r5_query_aware | 2,508 | 2,508 |

对账结果：`PASSED`；re-embedded=0、re-upserted=0、default partition unchanged。没有创建或删除 Collection/Partition，也没有向任何 Partition 写入。

## 16. 完整回归

| 检查 | 结果 |
| --- | --- |
| compileall app/scripts/tests | passed |
| Alembic heads/current | `20260712_0014 (head)` / `20260712_0014 (head)`；0014 属于后续 Task 25C，R6 自身未新增迁移 |
| targeted R6 tests | 16 passed |
| full pytest | 325 passed, 3 skipped, 4 deprecation warnings |
| 安全配置 | passed；真实外部调用默认 blocked |
| Secret Scan | passed_with_notes；9 个本地 `.env` 配置提示，0 blocking，未打印值 |
| 上传安全 | 11 passed |
| RBAC | 40 passed |
| DashVector Hybrid Flow | passed；fake/in-memory，无真实写入 |
| Multimodal Evidence / Agent | passed |
| Diagnosis/SOP/Task Agent | passed |
| Knowledge Curator | passed，正式知识计数未改 |
| Artifact Conversion / Concurrency | passed / passed |
| npm install / audit | passed；0 vulnerabilities |
| frontend build / vue-tsc | passed / passed |
| Playwright 浏览器审核 | 15/15 passed；console/page/network error 均为 0 |
| final smoke | 14/14 passed |

普通 pytest 没有调用真实 Qwen3、Embedding 或 DashVector。浏览器页面仅显示短 ID、排名、分数、状态和安全诊断，不显示 API Key、Authorization 或完整候选内部正文。

## 17. backend/.env 未修改

冻结前后 SHA-256 相等，对账项 `backend_env_unchanged=true`。仅 `.env.example` 增加了空值和说明；没有读取值到报告，也没有写真实 `.env`。

## 18. 正式全量重建未执行

`TASK25B_ALLOW_FULL_REINDEX=false`；formal full reindex=false。没有重新生成 Embedding，没有重新 upsert 向量。

## 19. expert_verified=false

本任务没有写 `expert_verified`，没有改变工程审批或任何知识审核状态。

## 20. 未打包

未生成 ZIP。冻结的 3 个历史 ZIP 文件在结束对账时大小和 SHA-256 均未变化。

## 21. 未提交 Git

未执行 `git add`、`commit`、`reset`、`clean` 或 `restore`。结束对账时 staged files=0；工作区原有及本任务改动均保留在本地。

## 后续动作

由用户或环境管理员在安全配置渠道提供该 Workspace 的精确 `DASHSCOPE_RERANK_BASE_URL`，并显式启用 `DASHSCOPE_RERANK_ENABLED` 与 `RAG_DEDICATED_RERANK_ENABLED`；不要从其他业务空间推断 URL。随后依次重跑 config check 和 20 条真实 Probe。只有 Probe 证明增益后，才可创建 R6 固定 Train/Dev 并进入两轮 Canary；只有 Canary 通过后，才可创建并运行一次 Formal 测试。
