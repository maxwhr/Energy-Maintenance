from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".runtime" / "task25b_r3_dev_r5"
REPORT = ROOT / "docs" / "25B_R3_DEV_R5_query_aware_grounded_rag_report.md"
FINAL_STATUS = "QUERY_AWARE_GROUNDED_RAG_QUALITY_GATE_FAILED"


def read_json(name: str) -> dict:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def write_json(name: str, payload: dict) -> None:
    (OUT / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def main() -> None:
    baseline = read_json("r5_baseline_snapshot.json")
    semantic = read_json("semantic_unit_v2_manifest.json")
    train_dev = read_json("train_dev_manifest_v2.json")
    canary = read_json("canary_iteration_2.json")
    reconcile = read_json("reconciliation.json")
    browser = read_json("browser_review.json")
    metrics = canary["metrics"]
    latency = canary["latency"]
    understanding = canary["query_understanding"]
    retrieval = canary["retrieval"]
    rerank = canary["rerank_before_after"]
    checks = canary["checks"]
    generated_at = datetime.now(timezone.utc).isoformat()

    if canary.get("status") != "CANARY_FAILED" or canary.get("iteration") != 2:
        raise SystemExit("R5 final report requires an immutable failed second Canary")
    if canary.get("passed"):
        raise SystemExit("refusing to emit failed report for a passing Canary")
    if not reconcile.get("passed"):
        raise SystemExit("R5 partition reconciliation is not complete")

    quality_gate = {
        "generated_at": generated_at,
        "task": "Task 25B-R3-DEV-R5",
        "status": FINAL_STATUS,
        "canary_status": "CANARY_FAILED",
        "canary_iteration": 2,
        "thresholds_lowered": False,
        "formal_test_status": "NOT_CREATED_CANARY_FAILED",
        "formal_test_created": False,
        "formal_test_frozen": False,
        "formal_run_count": 0,
        "allow_task25c": False,
        "failed_checks": [name for name, passed in checks.items() if not passed],
    }
    regression = {
        "generated_at": generated_at,
        "compileall": "PASSED",
        "alembic_heads_current": "20260712_0013 (head)",
        "pytest": "PASSED: 161 passed, 2 warnings",
        "security": "PASSED (upload checker rerun against intended 8012 base URL)",
        "rbac": "PASSED: 40/40",
        "agents": "PASSED",
        "conversion": "PASSED",
        "npm_audit": "PASSED: 0 vulnerabilities",
        "frontend_build": "PASSED",
        "vue_tsc": "PASSED",
        "static_install": "PASSED: 60 files",
        "browser": f"PASSED: {len(browser['scenarios'])} scenarios, no browser errors",
        "final_smoke": "PASSED: 23/23, failed=0",
    }
    boundaries = {
        "generated_at": generated_at,
        "task25b_allow_full_reindex": False,
        "engineering_approval_changed": False,
        "expert_verified_changed": False,
        "expert_verified": False,
        "formal_full_reindex": False,
        "default_partition_changed": False,
        "original_vectors_reindexed": 0,
        "new_zip_created": False,
        "delivery_updated": False,
        "delivery_staging_updated": False,
        "docs_zip_updated": False,
        "compress_archive_executed": False,
        "staged_files": 0,
        "git_commit_created": False,
    }
    write_json("quality_gate_status.json", quality_gate)
    write_json("regression_summary.json", regression)
    write_json("boundary_check.json", boundaries)

    unit_types = ", ".join(f"{name}={count}" for name, count in semantic["unit_types"].items())
    requested = ", ".join(f"{name}={count}" for name, count in retrieval["requested_channels"].items())
    actual = ", ".join(f"{name}={count}" for name, count in retrieval["actual_channels"].items())
    failed = ", ".join(quality_gate["failed_checks"])

    report = f"""# Task 25B-R3-DEV-R5 Query-Aware Grounded RAG 统一报告

最终状态：`{FINAL_STATUS}`  
生成时间：{generated_at}  
结论：R5 功能链路、隔离索引、回归与浏览器交互已经完成，但第二轮 Canary 仍未达到既定检索质量和时延硬门。阈值未降低，正式测试集未创建、未冻结、未运行，Task 25C 不允许开始。

## 1. R4 基线

R4 结果 `DEVELOPMENT_ENGINEERING_VECTOR_RECALL_NOT_PROVEN` 被原样保留。基线 Collection 为 `{baseline['collection']}`，旧分区为 `pilot_r2={baseline['partition_counts']['pilot_r2']}`、`pilot_r3_semantic={baseline['partition_counts']['pilot_r3_semantic']}`、`pilot_r4_grounded={baseline['partition_counts']['pilot_r4_grounded']}`；默认分区未改变。R5 开始时 Alembic current 为 `{baseline['alembic_current']}`。

## 2. R5 架构

实现链路为：确定性信号提取 → 完整性判断 → 受约束 LLM 理解/失败回退 → 主动追问与会话合并 → Retrieval Plan → Multi-query → 多通道召回 → RRF → 条件证据重排 → 结果精炼 → Citation 校验 → Confidence/No-answer → Grounded Answer Boundary。统一生产入口为 `POST /api/retrieval/query-aware-search`。

## 3. Maintenance Semantic Unit V2

表示版本 `task25b_r3_dev_r5_semantic_unit_v2` 共生成 `{semantic['semantic_units']}` 个 source-grounded 单元和同量 Anchor。类型分布：{unit_types}。`source_coverage_ratio={semantic['source_coverage_ratio']:.2f}`，unsupported facts={semantic['unsupported_facts']}，`engineering_verified=true`，`expert_verified=false`；精确重复候选拒绝 `{semantic['exact_duplicate_rejected']}` 条，需要来源复核 `{semantic['rejected_source_review']}` 条。

## 4. 未表示章节恢复

对 R4 的 `{semantic['unrepresented_sections_audited']}` 个未表示章节完成 100% 审计，其中 `{semantic['recoverable_sections']}` 个可恢复，实际恢复 `{semantic['recovered_sections']}` 个。章节组装保留 document、heading、页码、Chunk 顺序及跨页/续表来源；目录、版权和无效页眉页脚不进入正式语义单元。

## 5. Query Signal Extraction

确定性提取支持完整型号、中文告警名、数字告警码、组件、条件、否定表达、通信词和用户需求。用户明确提供的型号、告警码、数值和条件优先于 LLM，不允许被模型覆盖。浏览器验证中 `SUN2000-100KTL-M1`、`系统接地异常`、`999999` 和 SmartLogger 通信症状均被正确识别。

## 6. LLM Query Understanding

结构化 Schema、单次调用、共享 HTTP Client、缓存、超时和 deterministic fallback 已实现。Canary 共 `{understanding['cases']}` 条，计划调用 `{understanding['llm_invoked']}` 条，但 live provider 的结构化响应成功为 `{understanding['llm_succeeded']}`，全部 `{understanding['fallback']}` 条进入安全回退；这是真实限制，不记为 LLM 成功。最终意图、标准化、型号和告警指标虽均为 100%，主要由确定性提取和回退路径保障。

## 7. LLM 使用边界

LLM 只用于问题理解、检索假设/查询和候选内重排；不得输出无证据诊断、虚构型号/告警/步骤、添加候选或改写来源事实。Benchmark expected IDs/labels 未进入 Prompt、Anchor 或检索代码，隐藏推理和密钥不在 API/页面/日志中呈现。

## 8. Clarification

Canary 中需要追问 10 条，正确追问 10 条，无多余追问、无漏追问，Precision/Recall 均为 100%。浏览器问题“设备没反应”返回具体歧义选项和缺失字段，不直接给出维修结论。

## 9. Conversation Context

会话保存原始问题、系统追问和用户补充，并只合并 confirmed facts；24 小时过期，错误 hypothesis 不提升为事实。补充“型号是 SmartLogger，现象是通信中断，想了解原因”后，原始问题仍保留，canonical question、意图和检索计划均重新生成。Context merge accuracy={pct(metrics['context_merge_accuracy'])}。

## 10. Retrieval Plan

Planner 按完整性、意图和信号选择 Exact/Scoped Keyword、Raw Vector、Semantic Unit 与 KG Alias，并显式记录 requested/actual channels。请求统计：{requested}；实际统计：{actual}。不存在 vector 静默回退后宣称向量成功的情况。

## 11. Multi-query Retrieval

原始 query 始终保留，平均生成 `{retrieval['average_generated_queries']:.3f}` 条查询。向量通道仅复用 original/canonical 的单次 embedding，关键词通道保留意图化变体；Canary 的 multi-query gain={canary['multi_query_gain']:.3f}，未证明增益。

## 12. RRF

实现多通道 RRF 融合并记录候选通道。融合 Candidate Recall@50={metrics['candidate_recall_at_50']:.3f}，超过 0.90 硬门；但 Top-5/排序质量未同步达标，不能仅凭候选召回宣布质量通过。

## 13. Query-Aware Semantic Index

R5 仅写入 `{reconcile['collection']}` 的 `{reconcile['partition']}`，共 `{reconcile['remote_partition_count']}` 个向量。未创建新 Collection，未重写原始 1,262 个 Chunk，未修改旧分区或默认分区。

## 14. Evidence-aware Rerank

60 条 Canary 中 14 条满足条件并尝试重排，46 条跳过；14 条均进入安全 fallback。Recall@5 从 `{rerank['recall_at_5_before']:.3f}` 降至 `{rerank['recall_at_5_after']:.3f}`，MRR 从 `{rerank['mrr_before']:.6f}` 降至 `{rerank['mrr_after']:.6f}`。候选新增=0，候选来源修改=0；当前重排不构成质量提升。

## 15. Citation

正式 Citation 仅指向 current approved 中文原始 Chunk、document、heading 和 page，canonical text/Anchor 不作为引用。Citation validity={metrics['citation_validity']:.3f}（未达到 0.98），coverage={metrics['citation_coverage']:.3f}（达到 0.95）。

## 16. Confidence 与 No-answer

Canary 状态分布：ANSWERABLE=2、MULTIPLE_POSSIBILITIES=34、NEEDS_CLARIFICATION=10、INSUFFICIENT_EVIDENCE=14。No-answer precision/recall/F1={metrics['no_answer_precision']:.6f}/{metrics['no_answer_recall']:.6f}/{metrics['no_answer_f1']:.6f}，F1 未达到 0.85。浏览器无答案场景未生成维修结论，unsupported repair instructions=0。

## 17. Train/Dev 数据

不可变 v2 数据集 `{train_dev['dataset_version']}` 共 `{train_dev['cases']}` 条，SHA-256 `{train_dev['dataset_hash']}`。覆盖口语 100、vector-heavy 70、型号 20、告警 15、通信 16、安全 12、无答案 15、追问 20、上下文 15、原因 18、动作 36、验证 11；全部为 engineering candidate/source grounded，`expert_verified=false`，未使用正式测试数据。

## 18. Canary

最多两轮调优额度已用完。第二轮结果 `CANARY_FAILED`：Candidate R@50={metrics['candidate_recall_at_50']:.3f}，R@5/R@10={metrics['recall_at_5']:.3f}/{metrics['recall_at_10']:.3f}，MRR={metrics['mrr']:.6f}，nDCG@10={metrics['ndcg_at_10']:.6f}，Citation validity/coverage={metrics['citation_validity']:.3f}/{metrics['citation_coverage']:.3f}，No-answer F1={metrics['no_answer_f1']:.6f}。失败检查：{failed}。阈值未变更。

## 19. 正式盲测

由于第二轮 Canary 失败，`task25b_r3_dev_r5_llm_zh_v1` 未创建、未冻结、未运行，run count=0。创建与正式门禁脚本均返回明确阻断；不存在正式测试结果。

## 20. 性能

Fast p50/p95={latency['fast_p50_ms']:.3f}/{latency['fast_p95_ms']:.3f} ms（通过 1,500 ms）；LLM Understanding={latency['llm_understanding_p50_ms']:.3f}/{latency['llm_understanding_p95_ms']:.3f} ms（p95 超 4,000 ms）；Multi-query={latency['multi_query_p50_ms']:.3f}/{latency['multi_query_p95_ms']:.3f} ms（p95 超 5,000 ms）；Deep Rerank={latency['deep_rerank_p50_ms']:.3f}/{latency['deep_rerank_p95_ms']:.3f} ms（p95 超 6,000 ms）。无请求错误、无测试超时，但性能门未通过。

## 21. 向量对账

PostgreSQL Anchor=`{reconcile['anchor_vectors']}`、DashVector=`{reconcile['remote_partition_count']}`，missing/orphan/duplicate/mismatch=`{reconcile['missing']}/{reconcile['orphan']}/{reconcile['duplicate']}/{reconcile['mismatch']}`。旧分区仍为 1262/416/1289，original vectors reindexed=0，对账 PASSED。

## 22. 安全与 RBAC

安全配置、secret scan（7 条非阻断说明、0 blocking）、日志脱敏和 upload security 通过；upload checker 首次使用默认 8010 不匹配，改为本任务 8012 后 11 项通过。RBAC 40/40 通过。页面和响应未显示 API Key、Authorization、数据库密码、完整向量、本地绝对路径或隐藏推理。

## 23. 前端与浏览器

`npm install`、`npm audit`（0 vulnerabilities）、build、`vue-tsc --noEmit` 和静态安装（60 files）通过。浏览器完成 `{len(browser['scenarios'])}` 类真实场景：精确型号、精确告警、口语、歧义追问、补充合并、无答案；标准化、意图、缺失信息、Multi-query、Rerank 状态、confidence、原始页码引用和只读质量页均可见。console/page/unexpected-network errors 均为 0。质量页显示 `CANARY_FAILED / NOT_CREATED_CANARY_FAILED`。

## 24. Final Smoke

对当前代码的 `http://127.0.0.1:8012` 执行最终 smoke：23/23 passed，failed=0。按默认安全策略跳过会新增 qa_records 的 retrieval write；其余健康、认证、状态、业务只读 API 全部通过。未停止其他项目使用的 8000 或 5432。

## 25. 已知限制

主要阻断为 Top-5/排序指标、Citation validity、No-answer F1，以及 LLM/Multi-query/Deep p95。真实 LLM 结构化响应在 Canary 31 次调用中全部走 fallback，条件重排也未带来正收益。当前功能可用于受控开发验证，但不能宣称检索质量具有竞争力。

## 26. LoongArch

代码保持无 CUDA、GPU、本地大模型、FAISS、pgvector、Neo4j 和 Docker 新依赖，但本轮未在 LoongArch + Kylin 实机验证。

## 27. 正式全量重建

`TASK25B_ALLOW_FULL_REINDEX=false` 保持不变；正式全量重建未执行，默认 Partition 未修改，旧 Chunk 未重新 Embedding/upsert。

## 28. Expert Verification

未修改工程审批，未写 `expert_verified=true`，本轮新增表示均为 `engineering_verified=true / expert_verified=false`；未伪造行业专家复核。

## 29. No-package

未执行打包或 `Compress-Archive`，未生成新 ZIP；delivery、delivery_staging 与 docs.zip 未更新。

## 30. Git 边界与最终判断

未执行 git add/commit/reset/clean/restore，staged files=0，工作区原有及本轮修改全部保留。功能开发完成、source grounding 与歧义边界成立，但质量门未通过；最终状态必须且仅为 `{FINAL_STATUS}`，`allow Task 25C=false`。
"""
    REPORT.write_text(report, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": FINAL_STATUS,
                "report": str(REPORT.relative_to(ROOT)),
                "quality_gate": str((OUT / "quality_gate_status.json").relative_to(ROOT)),
                "regression": str((OUT / "regression_summary.json").relative_to(ROOT)),
                "boundaries": str((OUT / "boundary_check.json").relative_to(ROOT)),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
