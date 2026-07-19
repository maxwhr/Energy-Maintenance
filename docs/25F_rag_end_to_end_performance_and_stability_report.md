# Task 25F：RAG 端到端性能取证、并行化与稳定性专项报告

> 生成时间：2026-07-15T00:43:11.697692+00:00  
> 最终状态：`TASK25F_RAG_COMPATIBILITY_FAILED`  
> 判定：性能、SQL、并发、资源隔离和回归门通过；冻结基线要求的结果/Citation 100% 兼容门未通过，因此不得标记整体 PASS。

## 1. 执行摘要

固定查询集为 `task25f_rag_performance_suite_v1`，共 60 条，SHA-256 `7e7c6b225faf77770a21ebc67334943bb5fa5476e404a6164b3315c39971ff79`。cache-off 总延迟 p95 从 3762.349 ms 降至 2879.420 ms，改善 23.47%；SQL p95 从 15 条降至 8 条，SQL 累计耗时 p95 为 215.031 ms。

真实 provider 仍是主瓶颈：按 p50 关键路径近似分解，provider 90.8%、PostgreSQL 2.8%、Python/融合/排序残差 6.4%。并行阶段会重叠，因此该分解使用 `embedding + max(raw vector, semantic unit)`，不把并发阶段累计耗时错误相加。连接池等待时间未被 SQLAlchemy 暴露，报告不伪造百分比。

完整并发矩阵为 `PASS`：20 并发 hybrid p95 5766.435 ms，错误/超时/DB 池耗尽/HTTP 池耗尽均为 0。相同向量请求通过 60 秒、有界、仅 ID/分数的 provider 查询合并层，将 1200 次逻辑向量操作合并为 39 次真实网络请求；数据库仍逐请求执行权限、审批和 scope 校验。

严格兼容门失败：candidate identity 41.67%、Top5/Top10/Citation 58.33%/58.33%/58.33%，但 query understanding/query variants/requested channels/confidence/no-answer/clarification/scope 均为 100%，scope leakage=0，未解释的相关证据损失=0。差异主要来自冻结基线与当前真实 DashVector 可用性、近似召回和部分 Semantic Unit 调用失败分布不同；不能把它改写成兼容 PASS。

## 2. Task 25E 结论与根因判断

Task 25E 已在同一 PostgreSQL 数据量下把 Record Center 从 2,100 条 SQL / 4,176.871 ms 降至 9 条 SQL / 27.818 ms，说明数据库记录数量本身不是延迟根因。本任务的 RAG 取证也得到同一结论：优化后 PostgreSQL 只占近似 p50 关键路径 2.8%，主要耗时位于真实 Embedding 和 DashVector 网络阶段。

根因与处理：

- 原多 query/channel 存在串行外呼；改为 `BoundedRetrievalExecutor`，channel/vector/query variant 并发上限均为 3，并保留局部失败结果。
- 原每请求存在重复原始 query embedding prefetch；移除后 embedding 逻辑调用从 77 降至 49，节省 28 次。
- 原 scope/candidate 数据会在多个阶段重复读取；改为一次 scope context、批量 candidate hydration、批量 evidence identity 和 feature context。
- Citation 构建改为使用已 hydration 的候选映射，Citation SQL 为 0。
- DashVector/Embedding HTTP client 改为进程级共享；连接不会随请求数线性增长。
- DashVector 近似召回在相同向量并发下会波动；增加有界 60 秒 provider query coalescing，仅保存向量 ID、分数与 metadata，不保存文档正文。
- 前端增加 200 ms debounce、相同 in-flight 去重、旧请求 AbortController 取消和离页取消。

## 3. 基线与优化后性能

| 指标 | 基线 | 优化后 |
|---|---:|---:|
| 总延迟 p50 | 2349.235 ms | 2017.276 ms |
| 总延迟 p95 | 3762.349 ms | 2879.420 ms |
| 最大延迟 | 5765.181 ms | 6548.622 ms |
| SQL 数 p50 / p95 | 12 / 15 | 7 / 8 |
| SQL 累计耗时 p95 | 7205.146 ms | 215.031 ms |
| provider 逻辑请求 p50 / p95 | 10 / 12 | 10 / 11 |
| 查询变体总数 | 221 | 221 unique |
| 每请求 pre-fusion / fused candidate 中位数 | 303 / 116 | 325.5 / 113.5 |

性能门：keyword fast p95 177.759 ms（≤800）、hybrid p95 2893.207 ms（≤3,000）、multi-query p95 2886.940 ms（≤4,000）、全体 p95 2879.420 ms（≤5,000），全部通过。

## 4. 阶段 Trace 与根因占比

| 阶段 | p50 | p95 | 最大值 |
|---|---:|---:|---:|
| embedding_ms | 515.371 ms | 576.430 ms | 2619.378 ms |
| raw_vector_ms | 481.663 ms | 816.509 ms | 2686.873 ms |
| semantic_unit_ms | 1296.612 ms | 1854.784 ms | 3416.440 ms |
| keyword_ms | 36.907 ms | 65.579 ms | 183.798 ms |
| rerank_ms | 42.076 ms | 76.525 ms | 233.068 ms |
| citation_ms | 0.120 ms | 0.312 ms | 1.162 ms |
| total_ms | 1996.056 ms | 2855.793 ms | 6494.957 ms |

近似关键路径占比：PostgreSQL 2.8%；provider 90.8%；Python/融合/排序残差 6.4%；pool wait 不可观测且未伪造。provider 的 `semantic_unit_ms` p50/p95 为 1296.612/1854.784 ms，是稳定态主要瓶颈。

## 5. SQL、批量 Hydration 与 Citation

优化后每请求 SQL p50/p95/max 为 7/8/8，查询预算通过；serializer SQL=0，N+1 warnings=0，scope query 每请求最多 1 次。

- Scope：一次解析并释放原请求事务连接，再以短 Session 加载只读 scope。
- Keyword：在同一 scope 候选集上预计算多变体排名，不重复扫描数据库。
- Candidate Hydration：Chunk/Document 与 Semantic Unit 均按 ID 集合批量读取，无 candidate loop SQL。
- Evidence Identity：批量映射，同一物理证据不会重复占位。
- Citation：复用 hydration 映射，SQL=0；locator 与审批/状态校验未关闭。
- EXPLAIN：NO_INDEX_MIGRATION_REQUIRED；最慢计划 12.542 ms；未增加索引或 Alembic migration，head 保持 `20260712_0015`。

## 6. Provider、并行和失败降级

| 操作 | 逻辑调用 | 成功 | 失败 | p50 | p95 |
|---|---:|---:|---:|---:|---:|
| embedding | 49 | 49 | 0 | 523.032 ms | 590.707 ms |
| raw_vector | 98 | 98 | 0 | 443.568 ms | 724.557 ms |
| semantic_unit | 330 | 309 | 21 | 455.986 ms | 615.964 ms |

Qwen3/MiniMax rerank/StepFun rerank 调用为 0/0/0。重试=0、timeout=0、429=0。真实 provider 成功取证与 10 个注入失败场景分开记录；失败注入不调用真实 provider。

失败降级：`PASS`，成功通道保留=True，未验证 Citation=0，无限重试=0，孤儿后台任务=0。

## 7. 冷启动、稳态与并发

进程首请求 7579.625 ms，第二请求 1292.359 ms，稳态 50 次 p50/p95 907.270/1547.376 ms，独立子进程 restart 首请求 6787.640 ms。启动阶段未做付费 API 预热或全语料加载。

| 并发 | hybrid p95 | 错误率 | 超时率 | 响应变异 |
|---:|---:|---:|---:|---:|
| 1 | 1457.631 ms | 0.00% | 0.00% | 0 |
| 5 | 2246.652 ms | 0.00% | 0.00% | 0 |
| 10 | 3334.323 ms | 0.00% | 0.00% | 0 |
| 20 | 5766.435 ms | 0.00% | 0.00% | 0 |

DB pool max checked-out=15、max overflow=10；HTTP client 实例数=1；cross-request contamination=0，cross-user cache leakage=0。

## 8. 响应与质量兼容

| 字段 | 兼容率 |
|---|---:|
| query_understanding | 100.00% |
| query_variants | 100.00% |
| requested_channels | 100.00% |
| actual_channels | 60.00% |
| candidate_identities | 41.67% |
| top5_identities | 58.33% |
| top10_identities | 58.33% |
| citation_identities | 58.33% |
| citation_locators | 58.33% |
| confidence_status | 100.00% |
| no_answer | 100.00% |
| needs_clarification | 100.00% |
| scope_leakage | 100.00% |

candidate loss 计数=536，但 `unexplained_relevant_evidence_loss=0`；该计数不能代替人工相关性判断。由于 identity/Citation 严格兼容率未达 100%，响应兼容和质量兼容均判 FAIL。

## 9. 前端、浏览器与权限

独立 Playwright/Chromium 浏览器审核 `PASS`，22 项检查全部通过；预期取消请求 7 次。覆盖 exact/hybrid/multi-query、主动追问、无答案边界、Citation、debounce/in-flight 去重、旧请求/离页取消、admin 性能摘要、viewer 面板隐藏与 403。普通用户响应不含内部 trace。

应用内浏览器运行时因 `Cannot redefine property: process` 阻塞（`BLOCKED_CANNOT_REDEFINE_PROCESS`）；这属于审核工具 bootstrap 故障，未被伪报为应用内浏览器 PASS。真实页面验收由独立 Playwright 完成。

## 10. 回归与完整性

| 回归组 | 结果 |
|---|---|
| compileall | PASS |
| Alembic 0015 | PASS |
| pytest 400 passed / 3 skipped | PASS |
| 安全 | PASS |
| RBAC | PASS |
| RAG flow | PASS |
| Agents | PASS |
| Conversion | PASS |
| Task 25D frozen/mandated regression | PASS |
| Task 25E frozen PASS evidence | PASS |
| npm audit | PASS |
| frontend build/vue-tsc/static install | PASS |
| browser | PASS |
| final smoke | PASS |

只读对账 `PASSED`：documents/chunks/active/semantic anchors 为 372/4791/2882/4213；分区为 pilot_r2=1262、pilot_r3=416、pilot_r4=1289、pilot_r5=2508。Embedding/vector writes=0/0，默认 partition 未变，审批/expert_verified 未变，staged=0。

强制安全/RBAC 回归产生的临时 `Task24D_*` 上传已由精确夹具清理器移除；最后一次补跑删除 4 份，formal_documents_deleted=0，最终文档/Chunk 数与冻结值完全一致。Task 25D regression runtime 因任务要求执行回归而刷新，当前状态 PASS；报告与受保护状态证据保持。Task 25E 仅核对冻结 `result.json`/报告 PASS，不再次运行会覆盖其 runtime 的全套 writer。

## 11. 边界与后续建议

- Task 25C 保持 `MULTIMODAL_BENCHMARK_INSUFFICIENT`。
- R6 保持 `DEFERRED_QWEN3_RERANK_CONFIG`，Qwen3 probe/canary/formal 均未恢复。
- 未重新生成 Embedding，未 upsert/删除向量，未改 Collection/Partition，未执行正式全量重建。
- `TASK25B_ALLOW_FULL_REINDEX=false`；未修改 `backend/.env`。
- LoongArch + 银河麒麟未实机；未打包、未生成 ZIP、未 git add/commit。
- 性能工程可进入 LoongArch 准备，但发布前仍必须解决或批准 strict identity/Citation 兼容差异；不得以性能门通过替代质量签字。

## 12. Task 25F Result

### 1. Final Status
- result: `TASK25F_RAG_COMPATIBILITY_FAILED`
- performance forensics: PASS
- SQL optimization: PASS
- provider optimization: PASS
- channel parallelism: PASS
- candidate hydration: PASS
- citation batching: PASS
- response compatibility: FAIL
- quality compatibility: FAIL (strict identity/Citation gate)
- full reindex: NOT EXECUTED

### 2. Baseline
- performance suite: `task25f_rag_performance_suite_v1` / `7e7c6b225faf77770a21ebc67334943bb5fa5476e404a6164b3315c39971ff79`
- cases: 60
- total p50: 2349.235 ms
- total p95: 3762.349 ms
- SQL count: p50 12, p95 15
- SQL total p95: 7205.146 ms (concurrent statement sum)
- provider requests: p50 10, p95 12
- provider total p95: 8877.271 ms (concurrent call sum)
- query variants: 221
- candidates before/after fusion: median 303 / 116

### 3. Root Causes
- PostgreSQL percentage: ~2.8% (p50 critical-path approximation)
- provider percentage: ~90.8%
- pool wait percentage: N/A; unavailable, not fabricated; exhaustion=0
- Python processing percentage: ~6.4% residual
- query variant duplication: 0 normalized duplicates in final suite
- embedding duplication: 28 unnecessary prefetch calls removed
- channel serialization: removed with bounded parallelism
- candidate hydration N+1: removed; batched
- citation N+1: removed; Citation SQL=0
- serializer SQL: 0
- frontend duplicate requests: prevented by debounce/in-flight dedup/abort

### 4. SQL
- total SQL count: p50 7, p95 8, max 8
- scope SQL: 1/request
- keyword SQL: shared scope candidate scan; no per-variant SQL loop
- hydration SQL: bounded batch loads; no candidate loop
- citation SQL: 0
- serializer SQL: 0
- N+1 warnings: 0
- query budget: PASS

### 5. Provider
- embedding calls: 49 logical / 49 success
- raw vector calls: 98 logical
- semantic unit calls: 330 logical; 21 partial failures
- Qwen3 calls: 0
- MiniMax rerank calls: 0
- StepFun rerank calls: 0
- client instances: DashVector 1 shared endpoint client; Embedding 1 shared sync client
- connection reuse: true
- retries: 0
- timeouts: 0
- 429: 0
- p50: worst operation 523.032 ms
- p95: worst operation 724.557 ms

### 6. Parallelism
- channel concurrency: 3
- vector concurrency: 3 per request; process provider cap 24
- query variant concurrency: 3
- bounded: true
- stable ordering: PASS in concurrency matrix
- partial failure preservation: PASS (10 injected scenarios)
- request cancellation: PASS

### 7. Candidate Pipeline
- generated variants: 221
- unique variants: 221
- duplicate variants: 0
- embedding calls saved: 28
- provider calls saved: 28
- candidates hydrated: median 113.5, max 150
- hydration SQL: batch only
- evidence identities: 6447 fused across 60 cases
- feature calculations reused: request-local CandidateFeatureContext
- citation SQL: 0

### 8. Performance
- keyword fast path p50/p95: 154.469/177.759 ms
- hybrid p50/p95: 2165.838/2893.207 ms
- multi-query p50/p95: 2081.060/2886.940 ms
- cold p95: first process request 7579.625 ms; restart request 6787.640 ms
- warm p95: steady-50 1547.376 ms
- cache-off p95: 2879.420 ms
- cache-on p95: N/A (`TASK25F_CACHE_NOT_ENABLED`; full result cache disabled)
- improvement: 23.47%
- hard gate: PASS

### 9. Concurrency
- 1 concurrent p95: 1457.631 ms (hybrid)
- 5 concurrent p95: 2246.652 ms (hybrid)
- 10 concurrent p95: 3334.323 ms (hybrid)
- 20 concurrent p95: 5766.435 ms (hybrid)
- error rate: 0
- timeout rate: 0
- database pool exhaustion: 0
- HTTP pool exhaustion: 0
- cross-request leakage: 0

### 10. Compatibility
- query understanding parity: 100.00%
- query variant parity: 100.00%
- candidate identity parity: 41.67%
- Top5 parity: 58.33%
- Top10 parity: 58.33%
- citation identity parity: 58.33%
- citation locator parity: 58.33%
- confidence parity: 100.00%
- no-answer parity: 100.00%
- clarification parity: 100.00%
- scope leakage: 0
- relevant evidence loss: unexplained=0; raw identity loss count=536

### 11. Regression
- compileall: PASS
- Alembic: PASS, heads/current 20260712_0015
- pytest: PASS, 400 passed / 3 skipped
- security: PASS
- RBAC: PASS
- RAG flow: PASS
- agents: PASS
- conversion: PASS
- Task 25D: PASS (mandated retry refreshed regression evidence)
- Task 25E: PASS (frozen result/report read-only verification)
- npm audit: PASS, 0 vulnerabilities
- frontend: PASS (build/vue-tsc/static install)
- browser: standalone Playwright PASS; app-browser runtime BLOCKED (BLOCKED_CANNOT_REDEFINE_PROCESS)
- final smoke: PASS

### 12. Integrity
- pilot_r2 changed: no
- pilot_r3 changed: no
- pilot_r4 changed: no
- pilot_r5 changed: no
- default Partition changed: no
- embedding writes: 0
- vector writes: 0
- full reindex: no
- approval changed: no
- expert verification: unchanged / false

### 13. Boundaries
- Task 25C: `MULTIMODAL_BENCHMARK_INSUFFICIENT`
- R6 rerank: `DEFERRED_QWEN3_RERANK_CONFIG`
- LoongArch: not verified on real hardware
- package: no
- Git commit: no

### 14. Next Step
- RAG performance ready: yes, performance/stability gates passed
- database bottleneck confirmed: no; PostgreSQL is not the dominant bottleneck
- provider bottleneck confirmed: yes; real Embedding/DashVector dominates critical path
- allow LoongArch preparation: yes, with compatibility blocker retained
- return to Task 25C: only after explicit human decision
- return to R6: only after Qwen3 configuration is explicitly restored
- remaining blockers: strict candidate/Top5/Top10/Citation identity compatibility; app-browser runtime bootstrap defect; LoongArch real-machine acceptance
