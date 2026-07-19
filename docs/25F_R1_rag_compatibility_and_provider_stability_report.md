# Task 25F-R1：RAG 兼容性与 Provider 稳定性专项报告

> 生成时间：2026-07-15T02:24:44.113734+00:00  
> Task 25F 冻结状态：`TASK25F_RAG_COMPATIBILITY_FAILED`  
> Task 25F-R1 最终状态：`TASK25F_R1_COMPATIBILITY_PASS`

## 1. 执行结论

Task 25F-R1 已把“相同输入下的代码确定性”与“跨时点真实 ANN 返回”分开取证。相同 Raw Channel Snapshot 下，Sequential Reference 与 Optimized Replay 的候选、RRF、Top5、Top10、Citation、置信度、无答案、澄清和 Scope 全部达到 100% parity；30 个代表案例、每案例 3 次的真实 Provider A/A 也得到 Raw Vector 与 Semantic Unit exact parity 100%，当前局部失败为 0。因此本轮判定为 `TASK25F_R1_COMPATIBILITY_PASS`。

Task 25F 原始 `TASK25F_RAG_COMPATIBILITY_FAILED` 状态和原报告/result hash 均未改写。原任务比较的是两个不同时间点的真实近似检索，输入向量相同仍不等于外部索引内部执行状态、网络结果和局部失败状态相同；没有原始通道快照时，最终 TopK 差异无法单独证明代码回归。R1 的正确代码兼容门是“同一不可变 Raw Snapshot 的确定性回放”，真实 Provider 则由独立 A/A 稳定性门和业务质量门约束。

当前可接受 RAG 兼容性和性能工程结果，并允许进入 LoongArch 准备；这不等于完成 LoongArch 实机验收或生产发布签字。

## 2. 冻结边界与不可变证据

- 固定查询集：60 条；SHA-256 `7e7c6b225faf77770a21ebc67334943bb5fa5476e404a6164b3315c39971ff79`。
    - Task 25F manifest：`0d9dd4e2d73261d4e149999b0a07f5af4005b02397de54fcecc6d352ef2194a3`；原始报告和 result 保持 hash 不变。
- Alembic heads/current：`20260712_0015`。
- `backend/.env`：hash 未变；未输出 API Key 或 Authorization。
- 正式文档、Chunk、Semantic Unit、工程批准、`expert_verified`：Task 25F-R1 写入均为 0；冻结计数保持不变。
- `TASK25B_ALLOW_FULL_REINDEX=false`；未执行 Embedding 重建、向量 upsert、Collection/Partition 创建删除、默认 Partition 切换或正式全量重建。
- `.runtime/task25f/` 的受保护 Task 25F 证据通过 hash 复核；旧 Task 25F 回归 writer 未执行。
- 未打包、未生成 ZIP、未 git add/commit/reset/clean/restore。

## 3. Raw Channel Snapshot 协议与完整性

`RawRetrievalChannelSnapshot` 保存 snapshot/case/query hash、Scope fingerprint、planner/config version、通道、变体 hash、collection、partition、top_k、filter/vector/request hash、响应状态和候选的 ID/分数/排名/metadata hash。候选只保留 evidence source type、document/chunk/semantic-unit/section/source-chunk IDs；不保存完整向量、完整问题、候选正文、Provider 完整响应或凭据。

| 项目 | 结果 |
|---|---:|
| 案例 | 60 |
| 通道 | EXACT_KEYWORD, RAW_VECTOR, SCOPED_KEYWORD, SEMANTIC_UNIT |
| 原始通道记录 | 408 |
| 候选记录 | 25171 |
| Snapshot manifest hash | `1d5423ed63b8ea171d5866cf5fbfb1ab16456eea9c72c02ffc827475d5a2bf16` |
| Snapshot 文件 hash | `f23abc3b781d448749e3dd9d4ace4091a1e6ca0705382dc60a07f7d79e95f298` |
| 完整性 | PASSED |
| 无向量/问题/正文 | PASS |
| 回放 Provider 调用 | 0 |

## 4. Sequential Reference 与 Optimized Replay

Sequential Reference 使用固定通道顺序，关闭 Provider coalescing 和 embedding cache，仅消费冻结 Snapshot；Optimized Replay 使用同一 Snapshot 和 Task 25F 的批量 hydration、Evidence Identity、Citation、Candidate Feature Context 与本地并行步骤。两者均不访问真实 DashVector，也不生成 Embedding。

| 字段 | Parity |
|---|---:|
| Query Understanding | 100.00% |
| Query Variants | 100.00% |
| Requested / Actual Channels | 100.00% / 100.00% |
| Raw / Dedup Candidate Identity | 100.00% / 100.00% |
| RRF / Rerank / Refinement | 100.00% / 100.00% / 100.00% |
| Top5 / Top10 | 100.00% / 100.00% |
| Citation Identity / Locator | 100.00% / 100.00% |
| Confidence / No-answer / Clarification / Scope | 100.00% / 100.00% / 100.00% / 100.00% |

第一差异阶段：无；`first_divergent_stage_counts={}`，UNKNOWN=0，代码回归发现=NO。

## 5. Task 25F 历史差异逐阶段取证

历史 60 案例中有 35 个最终结果差异；13 个案例可关联 Provider partial failure，22 个案例只能分类为 `BASELINE_ARTIFACT_INCOMPLETE`。Task 25F 当时发生 21 个 Semantic Unit 失败事件，影响 17 个案例，但旧证据未保存原始通道响应、HTTP 状态或 provider code，不能事后伪造为 transient/permanent 或 ANN 波动。

R1 现有 Raw Snapshot 可把 QUERY_UNDERSTANDING、QUERY_VARIANTS、CHANNEL_REQUEST、CHANNEL_RAW_RESULT、CANDIDATE_MAPPING、EVIDENCE_IDENTITY、DEDUP、RRF、DETERMINISTIC_RERANK、REFINEMENT、HYDRATION、CITATION、CONFIDENCE 和 SERIALIZATION 逐段比较；当前没有任何第一差异阶段。

## 6. Coalescing Key、安全隔离与稳定排序

原 Task 25F 实现缺少显式 operation、embedding model/dimension、Scope、metric、index/config version 等 key 维度，也存在共享结果可变、首请求失败/取消/部分结果污染和等待者重复接管风险。本轮补齐以下安全约束，未改变 RAG 权重、Intent、Planner 或 Query Variant 语义。

| 审计项 | 结果 |
|---|---|
| provider/endpoint/collection | PASS |
| partition / top_k / filter | PASS / PASS / PASS |
| vector hash / Scope | PASS / PASS |
| model/dimension | PASS |
| operation/channel | PASS |
| index/config version | PASS / PASS |
| 失败/部分/取消不缓存 | PASS / PASS / PASS |
| 容量/TTL 有界 | PASS / PASS |
| 结果副本隔离 | PASS |
| 碰撞 / 跨用户泄漏 | 0 / 0 |

稳定排序使用显式 tie-break：通道内按 score 降序后 provider candidate ID；RRF 按 score、best channel rank、channel priority、evidence identity；确定性 rerank 补齐固定精度、实体匹配、原始 RRF rank 与 evidence identity；Citation 由最终候选顺序、来源优先级和稳定 locator/ID 决定。Python set/dict 或 asyncio 完成顺序不再作为业务排序条件。Evidence Identity、Hydration、Refinement、Citation 的回放 parity 均为 100%，Citation SQL=0。

## 7. 真实 Provider A/A 稳定性

测试覆盖 30 个代表案例、每例 3 次；同 query text/vector、collection、partition、top_k、filter、metadata 与客户端配置，A/A 时关闭 coalescing。Raw Vector 和 Semantic Unit 各 90 个配对。

| 指标 | Raw Vector | Semantic Unit |
|---|---:|---:|
| Exact Candidate Order | 100.00% | 100.00% |
| Exact Candidate Set | 100.00% | 100.00% |
| Top5 / Top10 | 100.00% / 100.00% | 100.00% / 100.00% |
| Jaccard@50 / RBO | 1.0 / 1.0 | 1.0 / 1.0 |
| Score drift mean/max | 0.0 / 0.0 | 0.0 / 0.0 |
| Direct evidence preservation | 100.00% | 100.00% |
| Availability / Failure rate | 100.00% / 0.00% | 100.00% / 0.00% |

结论：当前相同真实请求未观察到天然候选差异；Top5 与完整 Candidate Set 同为 100%，因此没有证据表明 Top5 “更稳定”，只能判定两者同样稳定；直接证据稳定。共享与独立 Client 的 10 次比较 exact order parity=100.00%，未观察到 Client 差异。当前 A/A 不能证明 Provider 波动，因而也不能把 Task 25F 的全部历史差异追溯归因于 Provider variance。

## 8. Semantic Unit 失败分类与有限重试

- 历史失败：21；UNKNOWN=21。原因是旧 trace 只保留 `VectorStoreAdapterError`，没有脱敏 HTTP/provider code。
- 历史分布：17 个唯一案例；两个案例发生多次失败，单案例最多 3 次。
- 当前 pre-retry / post-retry 失败：0 / 0；transient/permanent/configuration/mapping=0/0/0/0。
- 已启用最多 1 次有限重试，只允许 network connect/read、HTTP 429/502/503/504，使用小幅 jitter、总体请求预算和全局 Provider semaphore；400/401/403/404、filter/mapping/configuration/cancelled 均不重试。
- 本轮 retry success=0：因为当前没有瞬时失败，不把“零重试”伪装成重试修复收益；最终失败率=0%。

## 9. Live Quality Stability

| 指标 | Task 25F 冻结质量基线 | R1 当前 | 判定 |
|---|---:|---:|---|
| Candidate Recall | 0.978723 | 0.978723 | PASS |
| Recall@5 | 0.510638 | 0.531915 | PASS |
| MRR | 0.344554 | 0.345567 | PASS |
| nDCG@10 | 0.257237 | 0.24538 | observation |
| Citation validity / coverage | 1.0 / 1.0 | 1.0 / 1.0 | PASS |
| No-answer / Clarification | 1.0 / 0.983333 | 1.0 / 0.983333 | PASS |

Citation resolution=1.0；model/alarm hallucination=0/0；scope leakage=0；relevant evidence loss=0；provider errors=0。官方 Citation 中的跨型号来源提及不是生成式型号断言，不计为 hallucination。

nDCG@10 下降 -0.011857，这是明确保留的非硬门观察项。Task 25F-R1 指定的业务硬门是 Candidate Recall、Top5 直接证据、Citation、No-answer/Clarification、Scope、型号/告警幻觉和直接证据损失；这些全部通过。后续仍建议单独分析 nDCG 排位下降，不能隐藏该观察。

## 10. 性能保护

| 指标 | R1 | 门限 | 结果 |
|---|---:|---:|---|
| SQL p95 / max | 8.0 / 8.0 | <=8 | PASS |
| Citation SQL / N+1 | 0 / 0 | 0 / 0 | PASS |
| Keyword Fast p95 | 106.046 ms | <=800 ms | PASS |
| Hybrid warm p95 | 1543.184 ms | <=3000 ms | PASS |
| Multi-query warm p95 | 1484.351 ms | <=4000 ms | PASS |
| Full deterministic p95 | 4041.52 ms | <=5000 ms | PASS |
| 10 concurrent p95 | 4105.876 ms | <=5000 ms | PASS |
| 20 concurrent p95 | 6233.857 ms | <=7000 ms | PASS |
| error / timeout / pool exhaustion | 0 / 0 / 0 | 0 / 0 / 0 | PASS |

本轮没有发生有限重试样本，未把 retry 场景延迟混入正常稳态数据。

## 11. 向量只读对账与完整回归

只读对账 `PASSED`：documents/approved/chunks/active/semantic anchors=372/122/4791/2882/4213；pilot_r2/r3/r4/r5=1262/416/1289/2508。Embedding/vector writes=0/0，staged=0，Task 25C 与 R6 冻结证据未变。

| 回归组 | 结果 |
|---|---|
| compileall | PASS |
| Alembic 0015 | PASS |
| pytest | PASS（431 passed, 3 skipped） |
| security / RBAC | PASS / PASS |
| RAG / multimodal | PASS / PASS |
| agents / conversion | PASS / PASS |
| Task 25D / Task 25E | PASS / PASS（冻结 PASS 证据只读核验） |
| Task 25F frozen artifact | PASS（旧 writer 未运行） |
| frontend | NOT_REQUIRED（无前端状态展示改动） |
| final smoke | PASS |

安全/RBAC/RAG 流程创建的本轮测试文档由严格标记的 R1 专用清理器移除：正式文档删除 0，数据库文档数恢复为冻结值 372。没有用清理器触碰正式知识。

## 12. 保留状态、边界和剩余事项

- Task 25C：保持 `MULTIMODAL_BENCHMARK_INSUFFICIENT`，未修改。
- R6：保持 `DEFERRED_QWEN3_RERANK_CONFIG`，Qwen3/MiniMax/StepFun 未恢复。
- `expert_verified`：本任务写入 0，冻结状态未变；审批状态未变。
- LoongArch：允许进入准备，但尚未在 LoongArch + 银河麒麟实机验收，不能标记部署完成。
- package/ZIP/Git commit：均未执行。
- 剩余非阻断项：Task 25F 历史 21 次失败缺少细粒度错误码，无法追溯分类；旧 35 个差异没有原始通道快照，历史根因归属仍不完整；R1 当前 A/A 没有证明 Provider variance；nDCG@10 的 -0.011857 变化应继续独立观察。

## 13. Task 25F-R1 Result

### 1. Final Status
- result: `TASK25F_R1_COMPATIBILITY_PASS`
- deterministic replay: PASS
- provider A/A: PASS
- coalescing safety: PASS
- semantic provider stability: PASS
- live quality: PASS
- performance preservation: PASS
- full reindex: NOT EXECUTED

### 2. Snapshot
- cases: 60
- channels: EXACT_KEYWORD, RAW_VECTOR, SCOPED_KEYWORD, SEMANTIC_UNIT
- raw channel records: 408
- manifest hash: `1d5423ed63b8ea171d5866cf5fbfb1ab16456eea9c72c02ffc827475d5a2bf16`
- integrity: PASSED
- provider calls during replay: 0

### 3. Deterministic Replay
- candidate parity: 100.00%
- RRF parity: 100.00%
- Top5 parity: 100.00%
- Top10 parity: 100.00%
- Citation identity parity: 100.00%
- Citation locator parity: 100.00%
- confidence parity: 100.00%
- no-answer parity: 100.00%
- clarification parity: 100.00%
- scope parity: 100.00%
- first divergent stages: none

### 4. Coalescing Audit
- vector hash: PASS
- collection: PASS
- partition: PASS
- top_k: PASS
- filter: PASS
- scope: PASS
- model/dimension: PASS
- operation/channel: PASS
- cancellation: PASS
- failure caching: NOT CACHEABLE / PASS
- collisions: 0
- cross-user leakage: 0

### 5. Provider A/A
- cases: 30
- repetitions: 3
- raw vector exact parity: 100.00%
- raw vector Jaccard: 1.0
- semantic exact parity: 100.00%
- semantic Jaccard: 1.0
- Top5 stability: raw 100.00% / semantic 100.00%
- direct evidence preservation: raw 100.00% / semantic 100.00%
- provider failures: 0
- failure classes: {}

### 6. Semantic Unit Failures
- original failures: 21
- transient: 0
- permanent: 0
- configuration: 0
- mapping: 0
- retries enabled: YES, max 1 transient-only retry
- retry success: 0
- final failure rate: 0%

### 7. Live Quality
- Candidate Recall: 0.978723
- Recall@5: 0.531915
- MRR: 0.345567
- nDCG: 0.24538（delta -0.011857，非硬门观察）
- Citation validity: 1.0
- Citation coverage: 1.0
- no-answer: 1.0
- clarification: 0.983333
- model hallucination: 0
- alarm hallucination: 0
- scope leakage: 0
- relevant evidence loss: 0

### 8. Performance Preservation
- SQL p95: 8.0
- Citation SQL: 0
- Hybrid p95: 1543.184 ms
- Multi-query p95: 1484.351 ms
- 10 concurrent p95: 4105.876 ms
- 20 concurrent p95: 6233.857 ms
- error rate: 0%
- pool exhaustion: 0

### 9. Regression
- compileall: PASS
- Alembic: PASS / current `20260712_0015`
- pytest: PASS / 431 passed, 3 skipped
- security: PASS
- RBAC: PASS
- RAG: PASS
- agents: PASS
- conversion: PASS
- Task 25D: PASS
- Task 25E: PASS
- Task 25F frozen artifact: PASS
- final smoke: PASS

### 10. Integrity
- pilot_r2 changed: NO
- pilot_r3 changed: NO
- pilot_r4 changed: NO
- pilot_r5 changed: NO
- default Partition changed: NO
- embedding writes: 0
- vector writes: 0
- full reindex: NOT EXECUTED
- approval changed: NO
- expert verification: UNCHANGED / writes 0

### 11. Boundaries
- Task 25C: `MULTIMODAL_BENCHMARK_INSUFFICIENT` / UNCHANGED
- R6: `DEFERRED_QWEN3_RERANK_CONFIG` / UNCHANGED
- LoongArch: preparation allowed; physical acceptance not executed
- package: NOT EXECUTED
- Git commit: NOT EXECUTED

### 12. Final Judgment
- code regression found: NO
- provider variance proven: NO
- coalescing safe: YES
- compatibility accepted: YES
- RAG performance ready: YES
- allow LoongArch preparation: YES
- remaining blockers: no R1 hard blocker; historical failure telemetry/old raw-snapshot attribution gap, nDCG observation, and LoongArch physical acceptance remain follow-up items
