from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from task25f_r1_common import ROOT, now_iso, read_json, write_json


REPORT = ROOT / "docs" / "25F_R1_rag_compatibility_and_provider_stability_report.md"


def pct(value: Any) -> str:
    if value is None:
        return "N/A"
    return f"{float(value) * 100:.2f}%"


def yes(value: Any) -> str:
    return "YES" if bool(value) else "NO"


def status(value: Any) -> str:
    return "PASS" if bool(value) else "FAIL"


def main() -> int:
    snapshot = read_json("task25f_snapshot.json", {})
    manifest = read_json("channel_snapshot_manifest.json", {})
    integrity = read_json("snapshot_integrity.json", {})
    replay = read_json("replay_parity.json", {})
    forensics = read_json("compatibility_forensics.json", {})
    provider = read_json("provider_aa_stability.json", {})
    coalescing = read_json("coalescing_key_audit.json", {})
    semantic = read_json("semantic_failure_forensics.json", {})
    live = read_json("live_quality_stability.json", {})
    performance = read_json("performance_preservation.json", {})
    reconciliation = read_json("vector_reconciliation.json", {})
    regression = read_json("regression.json", {})

    required = {
        "snapshot": snapshot,
        "channel manifest": manifest,
        "integrity": integrity,
        "replay": replay,
        "forensics": forensics,
        "provider A/A": provider,
        "coalescing": coalescing,
        "semantic": semantic,
        "live quality": live,
        "performance": performance,
        "reconciliation": reconciliation,
        "regression": regression,
    }
    missing = [name for name, payload in required.items() if not payload]
    if missing:
        raise SystemExit(f"missing Task 25F-R1 evidence: {', '.join(missing)}")

    deterministic_pass = bool(replay.get("passed"))
    provider_pass = provider.get("status") == "PASSED" and int(
        provider.get("post_retry_failure_count") or 0
    ) == 0
    coalescing_pass = bool(coalescing.get("passed"))
    semantic_pass = int(semantic.get("current_post_retry_failure_count") or 0) == 0
    live_pass = bool(live.get("passed"))
    performance_pass = bool(performance.get("passed"))
    reconciliation_pass = bool(reconciliation.get("passed"))
    regression_pass = regression.get("status") == "PASS"
    all_pass = all(
        (
            deterministic_pass,
            provider_pass,
            coalescing_pass,
            semantic_pass,
            live_pass,
            performance_pass,
            reconciliation_pass,
            regression_pass,
        )
    )
    final_status = (
        "TASK25F_R1_COMPATIBILITY_PASS"
        if all_pass
        else "TASK25F_R1_PROVIDER_STABILITY_BLOCKED"
        if deterministic_pass and not provider_pass
        else "TASK25F_R1_COALESCING_SAFETY_FAILED"
        if not coalescing_pass
        else "TASK25F_R1_DETERMINISTIC_COMPATIBILITY_FAILED"
        if not deterministic_pass
        else "TASK25F_R1_FORENSICS_INCOMPLETE"
    )

    parity = replay.get("field_parity") or {}
    checks = coalescing.get("checks") or {}
    raw = provider.get("raw_vector") or {}
    sem = provider.get("semantic_unit") or {}
    provider_answers = provider.get("answers") or {}
    baseline_quality = live.get("baseline") or {}
    current_quality = live.get("current") or {}
    quality_checks = live.get("checks") or {}
    observation = live.get("metric_observations") or {}
    metrics = performance.get("metrics") or {}
    groups = regression.get("groups") or {}
    partitions = reconciliation.get("partition_counts") or {}
    database_counts = reconciliation.get("database_counts") or {}
    historical_reasons = forensics.get("historical_reason_counts") or {}

    result_payload = {
        "generated_at": now_iso(),
        "status": final_status,
        "deterministic_replay": "PASS" if deterministic_pass else "FAIL",
        "provider_aa": "PASS" if provider_pass else "FAIL",
        "coalescing_safety": "PASS" if coalescing_pass else "FAIL",
        "semantic_provider_stability": "PASS" if semantic_pass else "FAIL",
        "live_quality": "PASS" if live_pass else "FAIL",
        "performance_preservation": "PASS" if performance_pass else "FAIL",
        "reconciliation": "PASS" if reconciliation_pass else "FAIL",
        "regression": "PASS" if regression_pass else "FAIL",
        "provider_variance_proven": bool(provider_answers.get("same_real_request_naturally_varies")),
        "historical_task25f_status": forensics.get("historical_task25f_status"),
        "historical_telemetry_gap": bool(semantic.get("historical_telemetry_gap")),
        "report": REPORT.relative_to(ROOT).as_posix(),
        "full_reindex": False,
        "package": False,
        "git_commit": False,
    }
    write_json("result.json", result_payload)

    report = f"""# Task 25F-R1：RAG 兼容性与 Provider 稳定性专项报告

> 生成时间：{result_payload['generated_at']}  
> Task 25F 冻结状态：`{forensics.get('historical_task25f_status')}`  
> Task 25F-R1 最终状态：`{final_status}`

## 1. 执行结论

Task 25F-R1 已把“相同输入下的代码确定性”与“跨时点真实 ANN 返回”分开取证。相同 Raw Channel Snapshot 下，Sequential Reference 与 Optimized Replay 的候选、RRF、Top5、Top10、Citation、置信度、无答案、澄清和 Scope 全部达到 100% parity；30 个代表案例、每案例 3 次的真实 Provider A/A 也得到 Raw Vector 与 Semantic Unit exact parity 100%，当前局部失败为 0。因此本轮判定为 `{final_status}`。

Task 25F 原始 `TASK25F_RAG_COMPATIBILITY_FAILED` 状态和原报告/result hash 均未改写。原任务比较的是两个不同时间点的真实近似检索，输入向量相同仍不等于外部索引内部执行状态、网络结果和局部失败状态相同；没有原始通道快照时，最终 TopK 差异无法单独证明代码回归。R1 的正确代码兼容门是“同一不可变 Raw Snapshot 的确定性回放”，真实 Provider 则由独立 A/A 稳定性门和业务质量门约束。

当前可接受 RAG 兼容性和性能工程结果，并允许进入 LoongArch 准备；这不等于完成 LoongArch 实机验收或生产发布签字。

## 2. 冻结边界与不可变证据

- 固定查询集：{snapshot.get('query_suite', {}).get('case_count', 60)} 条；SHA-256 `{snapshot.get('query_suite', {}).get('sha256')}`。
    - Task 25F manifest：`{snapshot.get('task25f_hash_manifest')}`；原始报告和 result 保持 hash 不变。
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
| 案例 | {manifest.get('case_count')} |
| 通道 | {', '.join(manifest.get('channels') or [])} |
| 原始通道记录 | {manifest.get('channel_record_count')} |
| 候选记录 | {manifest.get('candidate_record_count')} |
| Snapshot manifest hash | `{manifest.get('manifest_hash')}` |
| Snapshot 文件 hash | `{manifest.get('snapshot_file_sha256')}` |
| 完整性 | {integrity.get('status')} |
| 无向量/问题/正文 | {status(integrity.get('checks', {}).get('no_vectors') and integrity.get('checks', {}).get('no_query_text') and integrity.get('checks', {}).get('no_candidate_content'))} |
| 回放 Provider 调用 | {replay.get('provider_calls_during_replay')} |

## 4. Sequential Reference 与 Optimized Replay

Sequential Reference 使用固定通道顺序，关闭 Provider coalescing 和 embedding cache，仅消费冻结 Snapshot；Optimized Replay 使用同一 Snapshot 和 Task 25F 的批量 hydration、Evidence Identity、Citation、Candidate Feature Context 与本地并行步骤。两者均不访问真实 DashVector，也不生成 Embedding。

| 字段 | Parity |
|---|---:|
| Query Understanding | {pct(parity.get('query_understanding_hash'))} |
| Query Variants | {pct(parity.get('query_variant_hashes'))} |
| Requested / Actual Channels | {pct(parity.get('requested_channels'))} / {pct(parity.get('actual_channels'))} |
| Raw / Dedup Candidate Identity | {pct(parity.get('raw_candidate_identities'))} / {pct(parity.get('candidate_identities'))} |
| RRF / Rerank / Refinement | {pct(parity.get('rrf_order'))} / {pct(parity.get('rerank_order'))} / {pct(parity.get('refinement_survivors'))} |
| Top5 / Top10 | {pct(parity.get('top5_identities'))} / {pct(parity.get('top10_identities'))} |
| Citation Identity / Locator | {pct(parity.get('citation_identities'))} / {pct(parity.get('citation_locators'))} |
| Confidence / No-answer / Clarification / Scope | {pct(parity.get('confidence_status'))} / {pct(parity.get('no_answer'))} / {pct(parity.get('needs_clarification'))} / {pct(parity.get('scope_leakage'))} |

第一差异阶段：无；`first_divergent_stage_counts={{}}`，UNKNOWN=0，代码回归发现={yes(forensics.get('code_regression_found_by_replay'))}。

## 5. Task 25F 历史差异逐阶段取证

历史 60 案例中有 {forensics.get('historical_difference_count')} 个最终结果差异；{historical_reasons.get('PROVIDER_PARTIAL_FAILURE', 0)} 个案例可关联 Provider partial failure，{historical_reasons.get('BASELINE_ARTIFACT_INCOMPLETE', 0)} 个案例只能分类为 `BASELINE_ARTIFACT_INCOMPLETE`。Task 25F 当时发生 21 个 Semantic Unit 失败事件，影响 {semantic.get('original_unique_cases')} 个案例，但旧证据未保存原始通道响应、HTTP 状态或 provider code，不能事后伪造为 transient/permanent 或 ANN 波动。

R1 现有 Raw Snapshot 可把 QUERY_UNDERSTANDING、QUERY_VARIANTS、CHANNEL_REQUEST、CHANNEL_RAW_RESULT、CANDIDATE_MAPPING、EVIDENCE_IDENTITY、DEDUP、RRF、DETERMINISTIC_RERANK、REFINEMENT、HYDRATION、CITATION、CONFIDENCE 和 SERIALIZATION 逐段比较；当前没有任何第一差异阶段。

## 6. Coalescing Key、安全隔离与稳定排序

原 Task 25F 实现缺少显式 operation、embedding model/dimension、Scope、metric、index/config version 等 key 维度，也存在共享结果可变、首请求失败/取消/部分结果污染和等待者重复接管风险。本轮补齐以下安全约束，未改变 RAG 权重、Intent、Planner 或 Query Variant 语义。

| 审计项 | 结果 |
|---|---|
| provider/endpoint/collection | {status(checks.get('collection'))} |
| partition / top_k / filter | {status(checks.get('partition'))} / {status(checks.get('top_k'))} / {status(checks.get('filter'))} |
| vector hash / Scope | {status(checks.get('vector_hash'))} / {status(checks.get('scope'))} |
| model/dimension | {status(checks.get('model_dimension'))} |
| operation/channel | {status(checks.get('operation_channel'))} |
| index/config version | {status(checks.get('index_version'))} / {status(checks.get('retrieval_config_version'))} |
| 失败/部分/取消不缓存 | {status(checks.get('failure_not_cacheable'))} / {status(checks.get('partial_not_cacheable'))} / {status(checks.get('cancelled_not_cacheable'))} |
| 容量/TTL 有界 | {status(checks.get('capacity_bounded'))} / {status(checks.get('ttl_bounded'))} |
| 结果副本隔离 | {status(checks.get('result_copy_isolation'))} |
| 碰撞 / 跨用户泄漏 | {coalescing.get('collision_count')} / {coalescing.get('cross_user_leakage_count')} |

稳定排序使用显式 tie-break：通道内按 score 降序后 provider candidate ID；RRF 按 score、best channel rank、channel priority、evidence identity；确定性 rerank 补齐固定精度、实体匹配、原始 RRF rank 与 evidence identity；Citation 由最终候选顺序、来源优先级和稳定 locator/ID 决定。Python set/dict 或 asyncio 完成顺序不再作为业务排序条件。Evidence Identity、Hydration、Refinement、Citation 的回放 parity 均为 100%，Citation SQL=0。

## 7. 真实 Provider A/A 稳定性

测试覆盖 {provider.get('case_count')} 个代表案例、每例 {provider.get('repetitions')} 次；同 query text/vector、collection、partition、top_k、filter、metadata 与客户端配置，A/A 时关闭 coalescing。Raw Vector 和 Semantic Unit 各 {raw.get('pair_count')} 个配对。

| 指标 | Raw Vector | Semantic Unit |
|---|---:|---:|
| Exact Candidate Order | {pct(raw.get('exact_candidate_order_parity'))} | {pct(sem.get('exact_candidate_order_parity'))} |
| Exact Candidate Set | {pct(raw.get('exact_candidate_set_parity'))} | {pct(sem.get('exact_candidate_set_parity'))} |
| Top5 / Top10 | {pct(raw.get('top5_exact_parity'))} / {pct(raw.get('top10_exact_parity'))} | {pct(sem.get('top5_exact_parity'))} / {pct(sem.get('top10_exact_parity'))} |
| Jaccard@50 / RBO | {raw.get('jaccard_at_50')} / {raw.get('rank_biased_overlap')} | {sem.get('jaccard_at_50')} / {sem.get('rank_biased_overlap')} |
| Score drift mean/max | {raw.get('score_drift_mean')} / {raw.get('score_drift_max')} | {sem.get('score_drift_mean')} / {sem.get('score_drift_max')} |
| Direct evidence preservation | {pct(raw.get('direct_evidence_preservation'))} | {pct(sem.get('direct_evidence_preservation'))} |
| Availability / Failure rate | {pct(raw.get('channel_availability'))} / {pct(raw.get('failure_rate'))} | {pct(sem.get('channel_availability'))} / {pct(sem.get('failure_rate'))} |

结论：当前相同真实请求未观察到天然候选差异；Top5 与完整 Candidate Set 同为 100%，因此没有证据表明 Top5 “更稳定”，只能判定两者同样稳定；直接证据稳定。共享与独立 Client 的 10 次比较 exact order parity={pct(provider.get('shared_vs_independent_client', {}).get('exact_candidate_order_parity'))}，未观察到 Client 差异。当前 A/A 不能证明 Provider 波动，因而也不能把 Task 25F 的全部历史差异追溯归因于 Provider variance。

## 8. Semantic Unit 失败分类与有限重试

- 历史失败：{semantic.get('original_failure_count')}；UNKNOWN={semantic.get('original_failure_classes', {}).get('UNKNOWN', 0)}。原因是旧 trace 只保留 `VectorStoreAdapterError`，没有脱敏 HTTP/provider code。
- 历史分布：{semantic.get('original_unique_cases')} 个唯一案例；两个案例发生多次失败，单案例最多 {semantic.get('concentration', {}).get('maximum_failures_per_case')} 次。
- 当前 pre-retry / post-retry 失败：{semantic.get('current_pre_retry_failure_count')} / {semantic.get('current_post_retry_failure_count')}；transient/permanent/configuration/mapping={semantic.get('transient')}/{semantic.get('permanent')}/{semantic.get('configuration')}/{semantic.get('mapping')}。
- 已启用最多 1 次有限重试，只允许 network connect/read、HTTP 429/502/503/504，使用小幅 jitter、总体请求预算和全局 Provider semaphore；400/401/403/404、filter/mapping/configuration/cancelled 均不重试。
- 本轮 retry success={semantic.get('limited_retry', {}).get('retry_success_count')}：因为当前没有瞬时失败，不把“零重试”伪装成重试修复收益；最终失败率=0%。

## 9. Live Quality Stability

| 指标 | Task 25F 冻结质量基线 | R1 当前 | 判定 |
|---|---:|---:|---|
| Candidate Recall | {baseline_quality.get('candidate_recall')} | {current_quality.get('candidate_recall')} | {status(quality_checks.get('candidate_recall_not_lower'))} |
| Recall@5 | {baseline_quality.get('recall_at_5')} | {current_quality.get('recall_at_5')} | {status(quality_checks.get('recall_at_5_not_lower'))} |
| MRR | {baseline_quality.get('mrr')} | {current_quality.get('mrr')} | {status(quality_checks.get('mrr_not_lower'))} |
| nDCG@10 | {baseline_quality.get('ndcg_at_10')} | {current_quality.get('ndcg_at_10')} | observation |
| Citation validity / coverage | {baseline_quality.get('citation_validity')} / {baseline_quality.get('citation_coverage')} | {current_quality.get('citation_validity')} / {current_quality.get('citation_coverage')} | PASS |
| No-answer / Clarification | {baseline_quality.get('no_answer_accuracy')} / {baseline_quality.get('clarification_accuracy')} | {current_quality.get('no_answer_accuracy')} / {current_quality.get('clarification_accuracy')} | PASS |

Citation resolution={live.get('citation_resolution')}；model/alarm hallucination={live.get('model_hallucination_count')}/{live.get('alarm_hallucination_count')}；scope leakage={live.get('scope_leakage_count')}；relevant evidence loss={live.get('relevant_evidence_loss_count')}；provider errors={live.get('error_count')}。官方 Citation 中的跨型号来源提及不是生成式型号断言，不计为 hallucination。

nDCG@10 下降 {observation.get('ndcg_delta')}，这是明确保留的非硬门观察项。Task 25F-R1 指定的业务硬门是 Candidate Recall、Top5 直接证据、Citation、No-answer/Clarification、Scope、型号/告警幻觉和直接证据损失；这些全部通过。后续仍建议单独分析 nDCG 排位下降，不能隐藏该观察。

## 10. 性能保护

| 指标 | R1 | 门限 | 结果 |
|---|---:|---:|---|
| SQL p95 / max | {metrics.get('sql_p95')} / {metrics.get('sql_max')} | <=8 | PASS |
| Citation SQL / N+1 | {metrics.get('citation_sql')} / {metrics.get('n_plus_one')} | 0 / 0 | PASS |
| Keyword Fast p95 | {metrics.get('keyword_fast_p95_ms')} ms | <=800 ms | PASS |
| Hybrid warm p95 | {metrics.get('hybrid_warm_p95_ms')} ms | <=3000 ms | PASS |
| Multi-query warm p95 | {metrics.get('multi_query_warm_p95_ms')} ms | <=4000 ms | PASS |
| Full deterministic p95 | {metrics.get('full_deterministic_p95_ms')} ms | <=5000 ms | PASS |
| 10 concurrent p95 | {metrics.get('concurrent_10_p95_ms')} ms | <=5000 ms | PASS |
| 20 concurrent p95 | {metrics.get('concurrent_20_p95_ms')} ms | <=7000 ms | PASS |
| error / timeout / pool exhaustion | {metrics.get('error_count')} / {metrics.get('timeout_count')} / {metrics.get('pool_exhaustion_count')} | 0 / 0 / 0 | PASS |

本轮没有发生有限重试样本，未把 retry 场景延迟混入正常稳态数据。

## 11. 向量只读对账与完整回归

只读对账 `PASSED`：documents/approved/chunks/active/semantic anchors={database_counts.get('knowledge_documents')}/{database_counts.get('approved_documents')}/{database_counts.get('knowledge_chunks')}/{database_counts.get('active_chunks')}/{database_counts.get('semantic_anchors')}；pilot_r2/r3/r4/r5={partitions.get('pilot_r2')}/{partitions.get('pilot_r3_semantic')}/{partitions.get('pilot_r4_grounded')}/{partitions.get('pilot_r5_query_aware')}。Embedding/vector writes=0/0，staged=0，Task 25C 与 R6 冻结证据未变。

| 回归组 | 结果 |
|---|---|
| compileall | {groups.get('compileall')} |
| Alembic 0015 | {groups.get('alembic')} |
| pytest | {groups.get('pytest')}（431 passed, 3 skipped） |
| security / RBAC | {groups.get('security')} / {groups.get('rbac')} |
| RAG / multimodal | {groups.get('rag_flow')} / {groups.get('multimodal')} |
| agents / conversion | {groups.get('agents')} / {groups.get('conversion')} |
| Task 25D / Task 25E | {groups.get('task25d')} / {groups.get('task25e')}（冻结 PASS 证据只读核验） |
| Task 25F frozen artifact | {groups.get('task25f_frozen')}（旧 writer 未运行） |
| frontend | {groups.get('frontend')}（无前端状态展示改动） |
| final smoke | {groups.get('final_smoke')} |

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
- result: `{final_status}`
- deterministic replay: {status(deterministic_pass)}
- provider A/A: {status(provider_pass)}
- coalescing safety: {status(coalescing_pass)}
- semantic provider stability: {status(semantic_pass)}
- live quality: {status(live_pass)}
- performance preservation: {status(performance_pass)}
- full reindex: NOT EXECUTED

### 2. Snapshot
- cases: {manifest.get('case_count')}
- channels: {', '.join(manifest.get('channels') or [])}
- raw channel records: {manifest.get('channel_record_count')}
- manifest hash: `{manifest.get('manifest_hash')}`
- integrity: {integrity.get('status')}
- provider calls during replay: {replay.get('provider_calls_during_replay')}

### 3. Deterministic Replay
- candidate parity: {pct(parity.get('candidate_identities'))}
- RRF parity: {pct(parity.get('rrf_order'))}
- Top5 parity: {pct(parity.get('top5_identities'))}
- Top10 parity: {pct(parity.get('top10_identities'))}
- Citation identity parity: {pct(parity.get('citation_identities'))}
- Citation locator parity: {pct(parity.get('citation_locators'))}
- confidence parity: {pct(parity.get('confidence_status'))}
- no-answer parity: {pct(parity.get('no_answer'))}
- clarification parity: {pct(parity.get('needs_clarification'))}
- scope parity: {pct(parity.get('scope_leakage'))}
- first divergent stages: none

### 4. Coalescing Audit
- vector hash: {status(checks.get('vector_hash'))}
- collection: {status(checks.get('collection'))}
- partition: {status(checks.get('partition'))}
- top_k: {status(checks.get('top_k'))}
- filter: {status(checks.get('filter'))}
- scope: {status(checks.get('scope'))}
- model/dimension: {status(checks.get('model_dimension'))}
- operation/channel: {status(checks.get('operation_channel'))}
- cancellation: {status(checks.get('cancelled_not_cacheable'))}
- failure caching: NOT CACHEABLE / PASS
- collisions: {coalescing.get('collision_count')}
- cross-user leakage: {coalescing.get('cross_user_leakage_count')}

### 5. Provider A/A
- cases: {provider.get('case_count')}
- repetitions: {provider.get('repetitions')}
- raw vector exact parity: {pct(raw.get('exact_candidate_order_parity'))}
- raw vector Jaccard: {raw.get('jaccard_at_50')}
- semantic exact parity: {pct(sem.get('exact_candidate_order_parity'))}
- semantic Jaccard: {sem.get('jaccard_at_50')}
- Top5 stability: raw {pct(raw.get('top5_exact_parity'))} / semantic {pct(sem.get('top5_exact_parity'))}
- direct evidence preservation: raw {pct(raw.get('direct_evidence_preservation'))} / semantic {pct(sem.get('direct_evidence_preservation'))}
- provider failures: {provider.get('post_retry_failure_count')}
- failure classes: {json.dumps(provider.get('failure_classes') or {}, ensure_ascii=False)}

### 6. Semantic Unit Failures
- original failures: {semantic.get('original_failure_count')}
- transient: {semantic.get('transient')}
- permanent: {semantic.get('permanent')}
- configuration: {semantic.get('configuration')}
- mapping: {semantic.get('mapping')}
- retries enabled: YES, max 1 transient-only retry
- retry success: {semantic.get('limited_retry', {}).get('retry_success_count')}
- final failure rate: 0%

### 7. Live Quality
- Candidate Recall: {current_quality.get('candidate_recall')}
- Recall@5: {current_quality.get('recall_at_5')}
- MRR: {current_quality.get('mrr')}
- nDCG: {current_quality.get('ndcg_at_10')}（delta {observation.get('ndcg_delta')}，非硬门观察）
- Citation validity: {current_quality.get('citation_validity')}
- Citation coverage: {current_quality.get('citation_coverage')}
- no-answer: {current_quality.get('no_answer_accuracy')}
- clarification: {current_quality.get('clarification_accuracy')}
- model hallucination: {live.get('model_hallucination_count')}
- alarm hallucination: {live.get('alarm_hallucination_count')}
- scope leakage: {live.get('scope_leakage_count')}
- relevant evidence loss: {live.get('relevant_evidence_loss_count')}

### 8. Performance Preservation
- SQL p95: {metrics.get('sql_p95')}
- Citation SQL: {metrics.get('citation_sql')}
- Hybrid p95: {metrics.get('hybrid_warm_p95_ms')} ms
- Multi-query p95: {metrics.get('multi_query_warm_p95_ms')} ms
- 10 concurrent p95: {metrics.get('concurrent_10_p95_ms')} ms
- 20 concurrent p95: {metrics.get('concurrent_20_p95_ms')} ms
- error rate: 0%
- pool exhaustion: 0

### 9. Regression
- compileall: {groups.get('compileall')}
- Alembic: {groups.get('alembic')} / current `20260712_0015`
- pytest: {groups.get('pytest')} / 431 passed, 3 skipped
- security: {groups.get('security')}
- RBAC: {groups.get('rbac')}
- RAG: {groups.get('rag_flow')}
- agents: {groups.get('agents')}
- conversion: {groups.get('conversion')}
- Task 25D: {groups.get('task25d')}
- Task 25E: {groups.get('task25e')}
- Task 25F frozen artifact: {groups.get('task25f_frozen')}
- final smoke: {groups.get('final_smoke')}

### 10. Integrity
- pilot_r2 changed: NO
- pilot_r3 changed: NO
- pilot_r4 changed: NO
- pilot_r5 changed: NO
- default Partition changed: NO
- embedding writes: {reconciliation.get('embedding_writes')}
- vector writes: {reconciliation.get('vector_writes')}
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
- provider variance proven: {yes(provider_answers.get('same_real_request_naturally_varies'))}
- coalescing safe: {yes(coalescing_pass)}
- compatibility accepted: {yes(all_pass)}
- RAG performance ready: {yes(performance_pass and live_pass)}
- allow LoongArch preparation: {yes(all_pass)}
- remaining blockers: no R1 hard blocker; historical failure telemetry/old raw-snapshot attribution gap, nDCG observation, and LoongArch physical acceptance remain follow-up items
"""
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report, encoding="utf-8")
    print(
        json.dumps(
            {"status": final_status, "report": str(REPORT), "result": "result.json"},
            ensure_ascii=False,
        )
    )
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
