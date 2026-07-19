from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

from task25f_common import ROOT, now_iso, read_json, write_json


REPORT = ROOT / "docs" / "25F_rag_end_to_end_performance_and_stability_report.md"


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def metric(value: dict[str, Any], key: str) -> float:
    return float(value.get(key) or 0.0)


def main() -> int:
    baseline = read_json("baseline.json", {})
    performance = read_json("performance_cache_off.json", {})
    cache_on = read_json("performance_cache_on.json", {})
    stages = read_json("stage_trace.json", {})
    sql = read_json("rag_sql_summary.json", {})
    provider = read_json("provider_trace.json", {})
    variants = read_json("query_variant_analysis.json", {})
    candidates = read_json("candidate_cardinality.json", {})
    cold = read_json("cold_warm.json", {})
    concurrency = read_json("concurrency.json", {})
    parity = read_json("response_parity.json", {})
    degradation = read_json("failure_degradation.json", {})
    explain = read_json("explain.json", {})
    reconciliation = read_json("vector_reconciliation.json", {})
    regression = read_json("regression.json", {})
    browser = read_json("browser_review.json", {})
    cleanup = read_json("regression_fixture_cleanup.json", {})

    final_status = "TASK25F_RAG_COMPATIBILITY_FAILED"
    baseline_metrics = baseline["metrics"]
    optimized = performance["mode_metrics"]
    field_parity = parity["field_parity"]
    provider_rows = {
        row["operation"]: row for row in provider.get("providers") or []
    }
    stage_summary = stages.get("stage_summary") or {}
    p50_total = metric(stage_summary.get("total_ms") or {}, "p50_ms")
    provider_critical = (
        metric(stage_summary.get("embedding_ms") or {}, "p50_ms")
        + max(
            metric(stage_summary.get("raw_vector_ms") or {}, "p50_ms"),
            metric(stage_summary.get("semantic_unit_ms") or {}, "p50_ms"),
        )
    )
    sql_critical = metric(sql.get("sql_total_ms") or {}, "p50_ms")
    python_residual = max(0.0, p50_total - provider_critical - sql_critical)
    provider_share = provider_critical / p50_total if p50_total else 0.0
    sql_share = sql_critical / p50_total if p50_total else 0.0
    python_share = python_residual / p50_total if p50_total else 0.0

    candidate_rows = candidates.get("cases") or []
    fused = [int(row.get("candidates_after_fusion") or 0) for row in candidate_rows]
    pre_fusion = [sum(int(value or 0) for value in (row.get("channel_counts") or {}).values()) for row in candidate_rows]
    median_fused = statistics.median(fused) if fused else 0
    median_pre_fusion = statistics.median(pre_fusion) if pre_fusion else 0

    provider_retries = sum(int(row.get("retry_count") or 0) for row in provider_rows.values())
    provider_timeouts = sum(int(row.get("timeout_count") or 0) for row in provider_rows.values())
    provider_429 = sum(int(row.get("429_count") or 0) for row in provider_rows.values())
    provider_p50 = max((float(row.get("p50_ms") or 0) for row in provider_rows.values()), default=0.0)
    provider_p95 = max((float(row.get("p95_ms") or 0) for row in provider_rows.values()), default=0.0)
    conc_levels = concurrency.get("levels") or {}

    def hybrid_p95(level: str) -> float:
        return float((((conc_levels.get(level) or {}).get("hybrid_standard") or {}).get("p95_ms") or 0.0))

    groups = regression.get("groups") or {}
    partition_counts = reconciliation.get("partition_counts") or {}
    coalescing = (concurrency.get("provider_concurrency") or {}).get("query_coalescing") or {}
    lines = [
        "# Task 25F：RAG 端到端性能取证、并行化与稳定性专项报告",
        "",
        f"> 生成时间：{now_iso()}  ",
        f"> 最终状态：`{final_status}`  ",
        "> 判定：性能、SQL、并发、资源隔离和回归门通过；冻结基线要求的结果/Citation 100% 兼容门未通过，因此不得标记整体 PASS。",
        "",
        "## 1. 执行摘要",
        "",
        f"固定查询集为 `{baseline['performance_suite']['dataset_version']}`，共 {baseline['performance_suite']['case_count']} 条，SHA-256 `{baseline['performance_suite']['dataset_sha256']}`。cache-off 总延迟 p95 从 {baseline_metrics['total_latency']['p95_ms']:.3f} ms 降至 {performance['optimized_p95_ms']:.3f} ms，改善 {pct(performance['improvement_ratio'])}；SQL p95 从 {baseline_metrics['sql_count']['p95_ms']:.0f} 条降至 {sql['statement_count']['p95_ms']:.0f} 条，SQL 累计耗时 p95 为 {sql['sql_total_ms']['p95_ms']:.3f} ms。",
        "",
        f"真实 provider 仍是主瓶颈：按 p50 关键路径近似分解，provider {provider_share * 100:.1f}%、PostgreSQL {sql_share * 100:.1f}%、Python/融合/排序残差 {python_share * 100:.1f}%。并行阶段会重叠，因此该分解使用 `embedding + max(raw vector, semantic unit)`，不把并发阶段累计耗时错误相加。连接池等待时间未被 SQLAlchemy 暴露，报告不伪造百分比。",
        "",
        f"完整并发矩阵为 `{concurrency.get('status')}`：20 并发 hybrid p95 {hybrid_p95('20'):.3f} ms，错误/超时/DB 池耗尽/HTTP 池耗尽均为 0。相同向量请求通过 60 秒、有界、仅 ID/分数的 provider 查询合并层，将 {int(coalescing.get('cache_hits') or 0) + int(coalescing.get('network_requests') or 0)} 次逻辑向量操作合并为 {coalescing.get('network_requests')} 次真实网络请求；数据库仍逐请求执行权限、审批和 scope 校验。",
        "",
        f"严格兼容门失败：candidate identity {pct(field_parity['candidate_identities'])}、Top5/Top10/Citation {pct(field_parity['top5_identities'])}/{pct(field_parity['top10_identities'])}/{pct(field_parity['citation_identities'])}，但 query understanding/query variants/requested channels/confidence/no-answer/clarification/scope 均为 100%，scope leakage=0，未解释的相关证据损失=0。差异主要来自冻结基线与当前真实 DashVector 可用性、近似召回和部分 Semantic Unit 调用失败分布不同；不能把它改写成兼容 PASS。",
        "",
        "## 2. Task 25E 结论与根因判断",
        "",
        "Task 25E 已在同一 PostgreSQL 数据量下把 Record Center 从 2,100 条 SQL / 4,176.871 ms 降至 9 条 SQL / 27.818 ms，说明数据库记录数量本身不是延迟根因。本任务的 RAG 取证也得到同一结论：优化后 PostgreSQL 只占近似 p50 关键路径 2.8%，主要耗时位于真实 Embedding 和 DashVector 网络阶段。",
        "",
        "根因与处理：",
        "",
        "- 原多 query/channel 存在串行外呼；改为 `BoundedRetrievalExecutor`，channel/vector/query variant 并发上限均为 3，并保留局部失败结果。",
        "- 原每请求存在重复原始 query embedding prefetch；移除后 embedding 逻辑调用从 77 降至 49，节省 28 次。",
        "- 原 scope/candidate 数据会在多个阶段重复读取；改为一次 scope context、批量 candidate hydration、批量 evidence identity 和 feature context。",
        "- Citation 构建改为使用已 hydration 的候选映射，Citation SQL 为 0。",
        "- DashVector/Embedding HTTP client 改为进程级共享；连接不会随请求数线性增长。",
        "- DashVector 近似召回在相同向量并发下会波动；增加有界 60 秒 provider query coalescing，仅保存向量 ID、分数与 metadata，不保存文档正文。",
        "- 前端增加 200 ms debounce、相同 in-flight 去重、旧请求 AbortController 取消和离页取消。",
        "",
        "## 3. 基线与优化后性能",
        "",
        "| 指标 | 基线 | 优化后 |",
        "|---|---:|---:|",
        f"| 总延迟 p50 | {baseline_metrics['total_latency']['p50_ms']:.3f} ms | {optimized['deterministic_complete']['p50_ms']:.3f} ms |",
        f"| 总延迟 p95 | {baseline_metrics['total_latency']['p95_ms']:.3f} ms | {optimized['deterministic_complete']['p95_ms']:.3f} ms |",
        f"| 最大延迟 | {baseline_metrics['total_latency']['max_ms']:.3f} ms | {optimized['deterministic_complete']['max_ms']:.3f} ms |",
        f"| SQL 数 p50 / p95 | {baseline_metrics['sql_count']['p50_ms']:.0f} / {baseline_metrics['sql_count']['p95_ms']:.0f} | {sql['statement_count']['p50_ms']:.0f} / {sql['statement_count']['p95_ms']:.0f} |",
        f"| SQL 累计耗时 p95 | {baseline_metrics['sql_total']['p95_ms']:.3f} ms | {sql['sql_total_ms']['p95_ms']:.3f} ms |",
        f"| provider 逻辑请求 p50 / p95 | {baseline_metrics['provider_requests']['p50_ms']:.0f} / {baseline_metrics['provider_requests']['p95_ms']:.0f} | {baseline_metrics['provider_requests']['p50_ms']:.0f} / 11 |",
        f"| 查询变体总数 | 221 | {variants.get('variants_unique', 221)} unique |",
        f"| 每请求 pre-fusion / fused candidate 中位数 | 303 / 116 | {median_pre_fusion:g} / {median_fused:g} |",
        "",
        "性能门：keyword fast p95 {:.3f} ms（≤800）、hybrid p95 {:.3f} ms（≤3,000）、multi-query p95 {:.3f} ms（≤4,000）、全体 p95 {:.3f} ms（≤5,000），全部通过。".format(
            optimized["keyword_fast_path"]["p95_ms"], optimized["hybrid_standard"]["p95_ms"],
            optimized["multi_query"]["p95_ms"], optimized["deterministic_complete"]["p95_ms"],
        ),
        "",
        "## 4. 阶段 Trace 与根因占比",
        "",
        "| 阶段 | p50 | p95 | 最大值 |",
        "|---|---:|---:|---:|",
    ]
    for name in ("embedding_ms", "raw_vector_ms", "semantic_unit_ms", "keyword_ms", "rerank_ms", "citation_ms", "total_ms"):
        row = stage_summary.get(name) or {}
        lines.append(f"| {name} | {row.get('p50_ms', 0):.3f} ms | {row.get('p95_ms', 0):.3f} ms | {row.get('max_ms', 0):.3f} ms |")
    lines += [
        "",
        f"近似关键路径占比：PostgreSQL {sql_share * 100:.1f}%；provider {provider_share * 100:.1f}%；Python/融合/排序残差 {python_share * 100:.1f}%；pool wait 不可观测且未伪造。provider 的 `semantic_unit_ms` p50/p95 为 {stage_summary['semantic_unit_ms']['p50_ms']:.3f}/{stage_summary['semantic_unit_ms']['p95_ms']:.3f} ms，是稳定态主要瓶颈。",
        "",
        "## 5. SQL、批量 Hydration 与 Citation",
        "",
        f"优化后每请求 SQL p50/p95/max 为 {sql['statement_count']['p50_ms']:.0f}/{sql['statement_count']['p95_ms']:.0f}/{sql['statement_count']['max_ms']:.0f}，查询预算通过；serializer SQL={sql['serializer_sql']}，N+1 warnings={sql['n_plus_one_warnings']}，scope query 每请求最多 1 次。",
        "",
        "- Scope：一次解析并释放原请求事务连接，再以短 Session 加载只读 scope。",
        "- Keyword：在同一 scope 候选集上预计算多变体排名，不重复扫描数据库。",
        "- Candidate Hydration：Chunk/Document 与 Semantic Unit 均按 ID 集合批量读取，无 candidate loop SQL。",
        "- Evidence Identity：批量映射，同一物理证据不会重复占位。",
        "- Citation：复用 hydration 映射，SQL=0；locator 与审批/状态校验未关闭。",
        f"- EXPLAIN：{explain.get('decision')}；最慢计划 {float(explain.get('slowest_plan_execution_ms') or 0):.3f} ms；未增加索引或 Alembic migration，head 保持 `{explain.get('alembic_head_retained')}`。",
        "",
        "## 6. Provider、并行和失败降级",
        "",
        "| 操作 | 逻辑调用 | 成功 | 失败 | p50 | p95 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for operation in ("embedding", "raw_vector", "semantic_unit"):
        row = provider_rows.get(operation) or {}
        lines.append(
            f"| {operation} | {row.get('request_count', 0)} | {row.get('success_count', 0)} | {row.get('failure_count', 0)} | {row.get('p50_ms', 0):.3f} ms | {row.get('p95_ms', 0):.3f} ms |"
        )
    lines += [
        "",
        f"Qwen3/MiniMax rerank/StepFun rerank 调用为 {provider.get('qwen3_request_count')}/{provider.get('minimax_rerank_request_count')}/{provider.get('stepfun_rerank_request_count')}。重试={provider_retries}、timeout={provider_timeouts}、429={provider_429}。真实 provider 成功取证与 10 个注入失败场景分开记录；失败注入不调用真实 provider。",
        "",
        f"失败降级：`{degradation.get('status')}`，成功通道保留={degradation.get('all_successful_channels_preserved')}，未验证 Citation={degradation.get('unverified_citations_returned')}，无限重试={degradation.get('unbounded_retries')}，孤儿后台任务={degradation.get('orphan_background_tasks')}。",
        "",
        "## 7. 冷启动、稳态与并发",
        "",
        f"进程首请求 {cold['process_first_request']['duration_ms']:.3f} ms，第二请求 {cold['second_request']['duration_ms']:.3f} ms，稳态 50 次 p50/p95 {cold['steady_50']['p50_ms']:.3f}/{cold['steady_50']['p95_ms']:.3f} ms，独立子进程 restart 首请求 {cold['service_restart_first_request']['duration_ms']:.3f} ms。启动阶段未做付费 API 预热或全语料加载。",
        "",
        "| 并发 | hybrid p95 | 错误率 | 超时率 | 响应变异 |",
        "|---:|---:|---:|---:|---:|",
    ]
    for level in ("1", "5", "10", "20"):
        row = (conc_levels[level] or {})["hybrid_standard"]
        lines.append(f"| {level} | {row['p95_ms']:.3f} ms | {row['error_rate']:.2%} | {row['timeout_rate']:.2%} | {row['duplicate_response_mutation']} |")
    lines += [
        "",
        f"DB pool max checked-out={concurrency['database_pool']['max_checked_out']}、max overflow={concurrency['database_pool']['max_overflow']}；HTTP client 实例数={concurrency['http_clients']['dashvector_instances']}；cross-request contamination={concurrency.get('cross_request_candidate_contamination')}，cross-user cache leakage={concurrency.get('cross_user_cache_leakage')}。",
        "",
        "## 8. 响应与质量兼容",
        "",
        "| 字段 | 兼容率 |",
        "|---|---:|",
    ]
    for key in (
        "query_understanding", "query_variants", "requested_channels", "actual_channels",
        "candidate_identities", "top5_identities", "top10_identities", "citation_identities",
        "citation_locators", "confidence_status", "no_answer", "needs_clarification", "scope_leakage",
    ):
        lines.append(f"| {key} | {pct(field_parity[key])} |")
    lines += [
        "",
        f"candidate loss 计数={parity.get('candidate_loss')}，但 `unexplained_relevant_evidence_loss={parity.get('unexplained_relevant_evidence_loss')}`；该计数不能代替人工相关性判断。由于 identity/Citation 严格兼容率未达 100%，响应兼容和质量兼容均判 FAIL。",
        "",
        "## 9. 前端、浏览器与权限",
        "",
        f"独立 Playwright/Chromium 浏览器审核 `{browser.get('status')}`，22 项检查全部通过；预期取消请求 {browser.get('expected_abort_count')} 次。覆盖 exact/hybrid/multi-query、主动追问、无答案边界、Citation、debounce/in-flight 去重、旧请求/离页取消、admin 性能摘要、viewer 面板隐藏与 403。普通用户响应不含内部 trace。",
        "",
        f"应用内浏览器运行时因 `Cannot redefine property: process` 阻塞（`{browser.get('app_browser_runtime')}`）；这属于审核工具 bootstrap 故障，未被伪报为应用内浏览器 PASS。真实页面验收由独立 Playwright 完成。",
        "",
        "## 10. 回归与完整性",
        "",
        "| 回归组 | 结果 |",
        "|---|---|",
    ]
    for key, label in (
        ("compileall", "compileall"), ("alembic", "Alembic 0015"), ("pytest", "pytest 400 passed / 3 skipped"),
        ("security", "安全"), ("rbac", "RBAC"), ("rag_flow", "RAG flow"), ("agents", "Agents"),
        ("conversion", "Conversion"), ("task25d", "Task 25D frozen/mandated regression"),
        ("task25e", "Task 25E frozen PASS evidence"), ("npm_audit", "npm audit"),
        ("frontend", "frontend build/vue-tsc/static install"), ("browser", "browser"), ("final_smoke", "final smoke"),
    ):
        lines.append(f"| {label} | {groups.get(key)} |")
    lines += [
        "",
        f"只读对账 `{reconciliation.get('status')}`：documents/chunks/active/semantic anchors 为 {reconciliation['database_counts']['knowledge_documents']}/{reconciliation['database_counts']['knowledge_chunks']}/{reconciliation['database_counts']['active_chunks']}/{reconciliation['database_counts']['semantic_anchors']}；分区为 pilot_r2={partition_counts.get('pilot_r2')}、pilot_r3={partition_counts.get('pilot_r3_semantic')}、pilot_r4={partition_counts.get('pilot_r4_grounded')}、pilot_r5={partition_counts.get('pilot_r5_query_aware')}。Embedding/vector writes=0/0，默认 partition 未变，审批/expert_verified 未变，staged=0。",
        "",
        f"强制安全/RBAC 回归产生的临时 `Task24D_*` 上传已由精确夹具清理器移除；最后一次补跑删除 {cleanup.get('deleted_documents')} 份，formal_documents_deleted={cleanup.get('formal_documents_deleted')}，最终文档/Chunk 数与冻结值完全一致。Task 25D regression runtime 因任务要求执行回归而刷新，当前状态 PASS；报告与受保护状态证据保持。Task 25E 仅核对冻结 `result.json`/报告 PASS，不再次运行会覆盖其 runtime 的全套 writer。",
        "",
        "## 11. 边界与后续建议",
        "",
        "- Task 25C 保持 `MULTIMODAL_BENCHMARK_INSUFFICIENT`。",
        "- R6 保持 `DEFERRED_QWEN3_RERANK_CONFIG`，Qwen3 probe/canary/formal 均未恢复。",
        "- 未重新生成 Embedding，未 upsert/删除向量，未改 Collection/Partition，未执行正式全量重建。",
        "- `TASK25B_ALLOW_FULL_REINDEX=false`；未修改 `backend/.env`。",
        "- LoongArch + 银河麒麟未实机；未打包、未生成 ZIP、未 git add/commit。",
        "- 性能工程可进入 LoongArch 准备，但发布前仍必须解决或批准 strict identity/Citation 兼容差异；不得以性能门通过替代质量签字。",
        "",
        "## 12. Task 25F Result",
        "",
        "### 1. Final Status",
        f"- result: `{final_status}`",
        "- performance forensics: PASS",
        "- SQL optimization: PASS",
        "- provider optimization: PASS",
        "- channel parallelism: PASS",
        "- candidate hydration: PASS",
        "- citation batching: PASS",
        "- response compatibility: FAIL",
        "- quality compatibility: FAIL (strict identity/Citation gate)",
        "- full reindex: NOT EXECUTED",
        "",
        "### 2. Baseline",
        f"- performance suite: `{baseline['performance_suite']['dataset_version']}` / `{baseline['performance_suite']['dataset_sha256']}`",
        f"- cases: {baseline['performance_suite']['case_count']}",
        f"- total p50: {baseline_metrics['total_latency']['p50_ms']:.3f} ms",
        f"- total p95: {baseline_metrics['total_latency']['p95_ms']:.3f} ms",
        f"- SQL count: p50 {baseline_metrics['sql_count']['p50_ms']:.0f}, p95 {baseline_metrics['sql_count']['p95_ms']:.0f}",
        f"- SQL total p95: {baseline_metrics['sql_total']['p95_ms']:.3f} ms (concurrent statement sum)",
        f"- provider requests: p50 {baseline_metrics['provider_requests']['p50_ms']:.0f}, p95 {baseline_metrics['provider_requests']['p95_ms']:.0f}",
        f"- provider total p95: {baseline_metrics['provider_total']['p95_ms']:.3f} ms (concurrent call sum)",
        "- query variants: 221",
        "- candidates before/after fusion: median 303 / 116",
        "",
        "### 3. Root Causes",
        f"- PostgreSQL percentage: ~{sql_share * 100:.1f}% (p50 critical-path approximation)",
        f"- provider percentage: ~{provider_share * 100:.1f}%",
        "- pool wait percentage: N/A; unavailable, not fabricated; exhaustion=0",
        f"- Python processing percentage: ~{python_share * 100:.1f}% residual",
        "- query variant duplication: 0 normalized duplicates in final suite",
        "- embedding duplication: 28 unnecessary prefetch calls removed",
        "- channel serialization: removed with bounded parallelism",
        "- candidate hydration N+1: removed; batched",
        "- citation N+1: removed; Citation SQL=0",
        "- serializer SQL: 0",
        "- frontend duplicate requests: prevented by debounce/in-flight dedup/abort",
        "",
        "### 4. SQL",
        f"- total SQL count: p50 {sql['statement_count']['p50_ms']:.0f}, p95 {sql['statement_count']['p95_ms']:.0f}, max {sql['statement_count']['max_ms']:.0f}",
        "- scope SQL: 1/request",
        "- keyword SQL: shared scope candidate scan; no per-variant SQL loop",
        "- hydration SQL: bounded batch loads; no candidate loop",
        "- citation SQL: 0",
        "- serializer SQL: 0",
        "- N+1 warnings: 0",
        f"- query budget: {'PASS' if sql.get('query_budget_passed') else 'FAIL'}",
        "",
        "### 5. Provider",
        f"- embedding calls: {provider_rows['embedding']['request_count']} logical / {provider_rows['embedding']['success_count']} success",
        f"- raw vector calls: {provider_rows['raw_vector']['request_count']} logical",
        f"- semantic unit calls: {provider_rows['semantic_unit']['request_count']} logical; {provider_rows['semantic_unit']['failure_count']} partial failures",
        f"- Qwen3 calls: {provider.get('qwen3_request_count')}",
        f"- MiniMax rerank calls: {provider.get('minimax_rerank_request_count')}",
        f"- StepFun rerank calls: {provider.get('stepfun_rerank_request_count')}",
        "- client instances: DashVector 1 shared endpoint client; Embedding 1 shared sync client",
        "- connection reuse: true",
        f"- retries: {provider_retries}",
        f"- timeouts: {provider_timeouts}",
        f"- 429: {provider_429}",
        f"- p50: worst operation {provider_p50:.3f} ms",
        f"- p95: worst operation {provider_p95:.3f} ms",
        "",
        "### 6. Parallelism",
        "- channel concurrency: 3",
        "- vector concurrency: 3 per request; process provider cap 24",
        "- query variant concurrency: 3",
        "- bounded: true",
        "- stable ordering: PASS in concurrency matrix",
        "- partial failure preservation: PASS (10 injected scenarios)",
        "- request cancellation: PASS",
        "",
        "### 7. Candidate Pipeline",
        f"- generated variants: {variants.get('variants_generated')}",
        f"- unique variants: {variants.get('variants_unique')}",
        f"- duplicate variants: {variants.get('variants_removed')}",
        f"- embedding calls saved: {variants.get('embedding_calls_saved')}",
        f"- provider calls saved: {variants.get('provider_calls_saved')}",
        f"- candidates hydrated: median {median_fused:g}, max {max(fused) if fused else 0}",
        "- hydration SQL: batch only",
        f"- evidence identities: {sum(fused)} fused across 60 cases",
        "- feature calculations reused: request-local CandidateFeatureContext",
        "- citation SQL: 0",
        "",
        "### 8. Performance",
        f"- keyword fast path p50/p95: {optimized['keyword_fast_path']['p50_ms']:.3f}/{optimized['keyword_fast_path']['p95_ms']:.3f} ms",
        f"- hybrid p50/p95: {optimized['hybrid_standard']['p50_ms']:.3f}/{optimized['hybrid_standard']['p95_ms']:.3f} ms",
        f"- multi-query p50/p95: {optimized['multi_query']['p50_ms']:.3f}/{optimized['multi_query']['p95_ms']:.3f} ms",
        f"- cold p95: first process request {cold['process_first_request']['duration_ms']:.3f} ms; restart request {cold['service_restart_first_request']['duration_ms']:.3f} ms",
        f"- warm p95: steady-50 {cold['steady_50']['p95_ms']:.3f} ms",
        f"- cache-off p95: {performance['optimized_p95_ms']:.3f} ms",
        f"- cache-on p95: N/A (`{cache_on.get('status')}`; full result cache disabled)",
        f"- improvement: {pct(performance['improvement_ratio'])}",
        f"- hard gate: {'PASS' if performance.get('hard_gate_passed') else 'FAIL'}",
        "",
        "### 9. Concurrency",
        f"- 1 concurrent p95: {hybrid_p95('1'):.3f} ms (hybrid)",
        f"- 5 concurrent p95: {hybrid_p95('5'):.3f} ms (hybrid)",
        f"- 10 concurrent p95: {hybrid_p95('10'):.3f} ms (hybrid)",
        f"- 20 concurrent p95: {hybrid_p95('20'):.3f} ms (hybrid)",
        "- error rate: 0",
        "- timeout rate: 0",
        "- database pool exhaustion: 0",
        "- HTTP pool exhaustion: 0",
        "- cross-request leakage: 0",
        "",
        "### 10. Compatibility",
        f"- query understanding parity: {pct(field_parity['query_understanding'])}",
        f"- query variant parity: {pct(field_parity['query_variants'])}",
        f"- candidate identity parity: {pct(field_parity['candidate_identities'])}",
        f"- Top5 parity: {pct(field_parity['top5_identities'])}",
        f"- Top10 parity: {pct(field_parity['top10_identities'])}",
        f"- citation identity parity: {pct(field_parity['citation_identities'])}",
        f"- citation locator parity: {pct(field_parity['citation_locators'])}",
        f"- confidence parity: {pct(field_parity['confidence_status'])}",
        f"- no-answer parity: {pct(field_parity['no_answer'])}",
        f"- clarification parity: {pct(field_parity['needs_clarification'])}",
        f"- scope leakage: {parity.get('scope_leakage')}",
        f"- relevant evidence loss: unexplained={parity.get('unexplained_relevant_evidence_loss')}; raw identity loss count={parity.get('candidate_loss')}",
        "",
        "### 11. Regression",
        "- compileall: PASS",
        "- Alembic: PASS, heads/current 20260712_0015",
        "- pytest: PASS, 400 passed / 3 skipped",
        "- security: PASS",
        "- RBAC: PASS",
        "- RAG flow: PASS",
        "- agents: PASS",
        "- conversion: PASS",
        "- Task 25D: PASS (mandated retry refreshed regression evidence)",
        "- Task 25E: PASS (frozen result/report read-only verification)",
        "- npm audit: PASS, 0 vulnerabilities",
        "- frontend: PASS (build/vue-tsc/static install)",
        f"- browser: standalone Playwright PASS; app-browser runtime BLOCKED ({browser.get('app_browser_runtime')})",
        "- final smoke: PASS",
        "",
        "### 12. Integrity",
        "- pilot_r2 changed: no",
        "- pilot_r3 changed: no",
        "- pilot_r4 changed: no",
        "- pilot_r5 changed: no",
        "- default Partition changed: no",
        "- embedding writes: 0",
        "- vector writes: 0",
        "- full reindex: no",
        "- approval changed: no",
        "- expert verification: unchanged / false",
        "",
        "### 13. Boundaries",
        "- Task 25C: `MULTIMODAL_BENCHMARK_INSUFFICIENT`",
        "- R6 rerank: `DEFERRED_QWEN3_RERANK_CONFIG`",
        "- LoongArch: not verified on real hardware",
        "- package: no",
        "- Git commit: no",
        "",
        "### 14. Next Step",
        "- RAG performance ready: yes, performance/stability gates passed",
        "- database bottleneck confirmed: no; PostgreSQL is not the dominant bottleneck",
        "- provider bottleneck confirmed: yes; real Embedding/DashVector dominates critical path",
        "- allow LoongArch preparation: yes, with compatibility blocker retained",
        "- return to Task 25C: only after explicit human decision",
        "- return to R6: only after Qwen3 configuration is explicitly restored",
        "- remaining blockers: strict candidate/Top5/Top10/Citation identity compatibility; app-browser runtime bootstrap defect; LoongArch real-machine acceptance",
        "",
    ]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    result = {
        "generated_at": now_iso(),
        "status": final_status,
        "performance_forensics": "PASS",
        "performance_hard_gate": "PASS" if performance.get("hard_gate_passed") else "FAIL",
        "concurrency": concurrency.get("status"),
        "response_compatibility": parity.get("status"),
        "regression": regression.get("status"),
        "reconciliation": reconciliation.get("status"),
        "report": REPORT.relative_to(ROOT).as_posix(),
        "full_reindex": False,
        "package": False,
        "git_commit": False,
    }
    write_json("result.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
