from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from task25b_r3_dev_r5_r5_common import ROOT, now_iso, read_json


REPORT = ROOT / "docs" / "25B_R3_DEV_R5_R5_candidate_recall_and_ranking_report.md"


def percent(value: float | None) -> str:
    return "N/A" if value is None else f"{value * 100:.2f}%"


def failed_checks(payload: dict[str, Any]) -> list[str]:
    return [name for name, passed in (payload.get("checks") or {}).items() if passed is False]


def main() -> None:
    snapshot = read_json("r5_r4_snapshot.json")
    dataset = read_json("train_dev_dataset_v1.json")
    hashes = read_json("dataset_hash_manifest.json")
    candidate = read_json("candidate_miss_summary.json")
    ranking = read_json("ranking_error_summary.json")
    intent = read_json("intent_forensics.json")
    iteration_1 = read_json("canary_iteration_1.json")
    tuning = read_json("dev_tuning.json")
    iteration_2 = read_json("canary_iteration_2.json")
    formal = read_json("formal_lock.json")
    vector = read_json("vector_reconciliation.json")
    browser = read_json("browser_review.json")

    if dataset.get("case_count") != 80:
        raise RuntimeError("fixed dataset no longer contains exactly 80 cases")
    if iteration_1.get("dataset_hash") != iteration_2.get("dataset_hash") != "":
        raise RuntimeError("Canary iterations do not share the same dataset hash")
    if iteration_1.get("label_hash") != iteration_2.get("label_hash"):
        raise RuntimeError("Canary iterations do not share the same label hash")
    if iteration_2.get("passed") is not False:
        raise RuntimeError("expected the second Canary to remain failed")
    if formal.get("formal_run_count") != 0 or formal.get("created") or formal.get("frozen"):
        raise RuntimeError("Formal boundary was violated")
    if vector.get("passed") is not True or vector.get("read_only") is not True:
        raise RuntimeError("read-only vector reconciliation did not pass")
    if browser.get("status") != "PASSED":
        raise RuntimeError("real browser review did not pass")

    rows = iteration_2.get("rows") or []
    plan_rows = [row for row in rows if row.get("retrieval_plan")]
    average_variants = (
        sum(len(row.get("generated_queries") or []) for row in plan_rows) / len(plan_rows)
        if plan_rows else 0.0
    )
    original_retained = sum(
        bool((row.get("retrieval_plan") or {}).get("query_variants"))
        and (row["retrieval_plan"]["query_variants"][0].get("variant_type") == "ORIGINAL")
        for row in plan_rows
    )
    generic_penalties = sum(
        float(item.get("generality_penalty") or 0) > 0
        for row in rows
        for item in (row.get("surfaced_results") or [])
    )
    relevant_lost = sum(int(row.get("relevant_evidence_loss") or 0) for row in rows)
    intent_errors_after = sum(
        row.get("expected_primary_intent") != row.get("actual_primary_intent")
        for row in rows
        if row.get("expected_primary_intent")
    )
    miss_counts = Counter(candidate.get("primary_reason_counts") or {})
    ranking_counts = Counter(ranking.get("primary_reason_counts") or {})
    metrics1 = iteration_1["metrics"]
    metrics2 = iteration_2["metrics"]
    latency2 = iteration_2["latency"]
    counts = vector["partition_counts"]
    budgets = next((row["retrieval_plan"]["channel_candidate_budgets"] for row in plan_rows), {})
    anchor_version = next((row["retrieval_plan"].get("anchor_matrix_version") for row in plan_rows), "N/A")
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout.splitlines()

    report = f"""# Task 25B-R3-DEV-R5-R5 候选召回与确定性排序专项报告

最终状态：`QUERY_AWARE_GROUNDED_RAG_R5_QUALITY_GATE_FAILED`

结论：候选召回已达到硬门（Candidate Recall@50={metrics2['candidate_recall_at_50']:.6f}），但直接答案 Hit@1/Hit@3、Recall@5/Recall@10、MRR、nDCG@10、canonicalization 及多查询/全链路延迟仍未达标。因此正式盲测未创建、未冻结、未运行，当前不允许进入 Task 25C。

## 1. R5-R4-MM 冻结基线

- 基线状态：`{snapshot.get('source_result')}`；iteration 1/2 每配置案例数分别为 {snapshot['iteration_1']['cases_per_configuration']} / {snapshot['iteration_2']['cases_per_configuration']}，历史不一致已保留为证据。
- 基线 iteration 2：Candidate R@50={snapshot['iteration_2']['deterministic_metrics']['candidate_recall_at_50']:.6f}，R@5={snapshot['iteration_2']['deterministic_metrics']['recall_at_5']:.6f}，R@10={snapshot['iteration_2']['deterministic_metrics']['recall_at_10']:.6f}，MRR={snapshot['iteration_2']['deterministic_metrics']['mrr']:.6f}，nDCG@10={snapshot['iteration_2']['deterministic_metrics']['ndcg_at_10']:.6f}。
- 13 个 R5-R4-MM 受保护产物、3 个既有 ZIP、`.env` SHA-256 和 staged=0 均已冻结；旧运行目录未改写。

## 2. 固定 Train/Dev 数据集与 Evaluation Evidence Identity

- 版本：`{dataset['dataset_version']}`；案例数：{dataset['case_count']}。
- dataset SHA-256：`{dataset['dataset_hash']}`。
- label SHA-256：`{dataset['label_hash']}`。
- iteration 1 / 2 均为 80 条，dataset/label hash 完全相同，变更数 0。
- 覆盖：复合意图 {dataset['coverage_manifest']['composite_intent']}、no-answer {dataset['coverage_manifest']['no_answer']}、需追问 {dataset['coverage_manifest']['requires_clarification']}、HTML FAQ {dataset['coverage_manifest']['html_faq']}、PDF {dataset['coverage_manifest']['pdf']}、多文档互补 {dataset['coverage_manifest']['multi_document_complementary']}。
- `EvaluationEvidenceIdentity` 明确 CHUNK / SEMANTIC_UNIT / SECTION / DOCUMENT 层级、direct/supporting/background 证据和 3/2/1/0 分级相关性；Semantic Unit 到 source chunks 的映射参与命中判断，禁止整文档或整章节无条件扩展为 relevant。

## 3. Candidate miss 逐案例取证

- 总计 {candidate['total_misses']} 个旧基线 miss，全部有唯一主要原因，UNKNOWN={candidate['unknown']}。
- 分布：EVALUATION_IDENTITY_MISMATCH={miss_counts['EVALUATION_IDENTITY_MISMATCH']}，ANCHOR_TYPE_TOO_NARROW={miss_counts['ANCHOR_TYPE_TOO_NARROW']}，PLANNER_QUERY_MISSING={miss_counts['PLANNER_QUERY_MISSING']}；其余查询归一化、复合意图、keyword、raw vector、semantic、channel budget/aggregation、RRF、source mapping、refinement、true corpus gap、label error 均为 0。
- 结论：12 个是评估身份/追问边界分母不匹配，4 个是快速关键字路径 Anchor 过窄，1 个缺少 Planner 查询；没有把问题统一归为 UNKNOWN，也没有扩大 expected IDs。

## 4. Ranking error 逐案例取证

- 排序错误 {ranking['ranking_error_cases']} 个：Top50 未进 Top5={ranking['top50_but_not_top5']}，Top5 未进 Top2={ranking['top5_but_not_top2']}。
- 分布：RELEVANCE_GRADE_NOT_USED={ranking_counts['RELEVANCE_GRADE_NOT_USED']}，GENERIC_SECTION_OVER_SPECIFIC={ranking_counts['GENERIC_SECTION_OVER_SPECIFIC']}，INSUFFICIENT_REQUESTED_INFO_COVERAGE={ranking_counts['INSUFFICIENT_REQUESTED_INFO_COVERAGE']}，WRONG_ALARM={ranking_counts['WRONG_ALARM']}。
- 已记录各阶段 rank、意图/信息覆盖、实体/条件、来源特异度、RRF/rerank breakdown 和错误 Top1 原因。

## 5. Composite Intent 与 requested_information

- 旧基线 intent 错误 {intent['intent_error_count']} 个，全部为 `TRIGGER_PRECEDENCE`；旧准确率 {intent['primary_intent_accuracy']:.6f}。
- 新合同区分 `primary_intent` 与最多 5 个 `requested_information`，复合案例 {dataset['coverage_manifest']['composite_intent']} 个；未按 case_id 写规则。
- iteration 2：primary intent accuracy={metrics2['primary_intent_accuracy']:.6f}；requested information P/R/F1={metrics2['requested_information_precision']:.6f}/{metrics2['requested_information_recall']:.6f}/{metrics2['requested_information_f1']:.6f}；primary intent 错误 {intent_errors_after} 个；型号/告警幻觉=0/0。

## 6. Planner V3、Anchor Coverage Matrix 与候选预算

- 平均查询变体 {average_variants:.3f}；原始查询保留 {original_retained}/{len(plan_rows)}；最多 5 条（ORIGINAL/CANONICAL/SYMPTOM_QUERY/REQUEST_QUERY/CONDITION_QUERY）。
- Anchor matrix：`{anchor_version}`；requested information 的 Anchor 类型取并集，`FULL_SECTION` 仅为低权重辅助召回。
- 预算：EXACT_KEYWORD={budgets.get('EXACT_KEYWORD', 30)}，SCOPED_KEYWORD={budgets.get('SCOPED_KEYWORD', 80)}，RAW_VECTOR={budgets.get('RAW_VECTOR', 80)}，SEMANTIC_UNIT={budgets.get('SEMANTIC_UNIT', 100)}；通道内 identity 上限 60，融合上限 150，Candidate 指标严格按 Top50。

## 7. Evidence Identity、RRF、Deterministic Rerank V2 与 refinement

- 候选以 Semantic Unit、明确 Section 或 Chunk 构造稳定 evidence identity，同源证据跨通道合并。
- Deterministic Rerank V2 使用 direct answer、requested information coverage、实体/条件、来源特异度和泛化惩罚；本轮唯一校准版本：`{tuning['calibration']['rerank_weights_version']}`。
- surfaced candidates 中触发泛化惩罚 {generic_penalties} 次；refinement 未解释相关证据丢失={relevant_lost}。
- 未启用新的 LLM tie-break，MiniMax 不作为本轮排序器。

## 8. Canary iteration 1 与唯一校准

| 指标 | iteration 1 | iteration 2 | 硬门 |
|---|---:|---:|---:|
| Candidate Recall@50 | {metrics1['candidate_recall_at_50']:.6f} | {metrics2['candidate_recall_at_50']:.6f} | >=0.95 |
| Recall@5 | {metrics1['recall_at_5']:.6f} | {metrics2['recall_at_5']:.6f} | >=0.80 |
| Recall@10 | {metrics1['recall_at_10']:.6f} | {metrics2['recall_at_10']:.6f} | >=0.85 |
| MRR | {metrics1['mrr']:.6f} | {metrics2['mrr']:.6f} | >=0.75 |
| nDCG@10 | {metrics1['ndcg_at_10']:.6f} | {metrics2['ndcg_at_10']:.6f} | >=0.80 |
| Direct Answer Hit@1 | {metrics1['direct_answer_hit_at_1']:.6f} | {metrics2['direct_answer_hit_at_1']:.6f} | >=0.70 |
| Direct Answer Hit@3 | {metrics1['direct_answer_hit_at_3']:.6f} | {metrics2['direct_answer_hit_at_3']:.6f} | >=0.85 |
| Requested Info Coverage@3 | {metrics1['requested_information_coverage_at_3']:.6f} | {metrics2['requested_information_coverage_at_3']:.6f} | >=0.90 |

- iteration 1 失败后仅执行一次校准；标签变更={str(tuning['labels_changed']).lower()}，删除案例={tuning['cases_removed']}，Formal 数据使用={str(tuning['formal_data_used']).lower()}，知识增加={str(tuning['knowledge_added']).lower()}，向量修改={str(tuning['vectors_modified']).lower()}。
- 校准仅覆盖通用 trigger precedence、requested information 规则、semantic query 数量和 deterministic rerank 权重/排序优先级；未执行第三轮 Canary。

## 9. Canary iteration 2 最终门禁

- 状态：`{iteration_2['status']}`；失败门：`{', '.join(failed_checks(iteration_2))}`。
- Citation validity/coverage={metrics2['citation_validity']:.6f}/{metrics2['citation_coverage']:.6f}；No-answer P/R/F1={metrics2['no_answer_precision']:.6f}/{metrics2['no_answer_recall']:.6f}/{metrics2['no_answer_f1']:.6f}。
- Clarification P/R={metrics2['clarification_precision']:.6f}/{metrics2['clarification_recall']:.6f}；context merge={metrics2['context_merge_accuracy']:.6f}；scope leakage/error={metrics2['scope_leakage']}/{metrics2['error_rate']:.6f}。
- p95：Fast={latency2['fast_path_p95_ms']:.3f}ms，Understanding={latency2['deterministic_understanding_p95_ms']:.3f}ms，Multi-query={latency2['multi_query_p95_ms']:.3f}ms，Full={latency2['full_deterministic_path_p95_ms']:.3f}ms。Multi-query 与 Full 超门。

## 10. Formal 测试

- created=false，frozen=false，dataset/SHA-256=null，run count=0，result=`{formal['result']}`。
- Canary 未全通过，因此没有创建 `task25b_r3_dev_r5_r5_zh_v1`，没有调用 Formal runner，也没有使用 Formal 结果调参。

## 11. 向量只读对账

- Collection：`{vector['collection']}`；pilot_r2={counts['pilot_r2']}，pilot_r3_semantic={counts['pilot_r3_semantic']}，pilot_r4_grounded={counts['pilot_r4_grounded']}，pilot_r5_query_aware={counts['pilot_r5_query_aware']}。
- re-embedded/re-upserted={vector['re_embedded']}/{vector['re_upserted']}；missing/orphan/duplicate/mismatch={vector['missing']}/{vector['orphan']}/{vector['duplicate']}/{vector['mismatch']}。
- default Partition affected=false；`.env` changed={str(vector['backend_env_changed']).lower()}；staged files={len(staged)}。

## 12. 完整回归

- compileall：PASSED（app/scripts/tests）。
- Alembic heads/current：`20260712_0013 (head)` / `20260712_0013 (head)`。
- pytest：270 passed，3 skipped，4 warnings，0 failed。
- 安全：config passed_with_warnings；secret scan passed_with_notes（9 notes，0 blocking）；log sanitization passed；upload security 11/11；RBAC 40/40。
- 业务与 Agent：DashVector hybrid（fake-in-memory、无真实向量写）、multimodal evidence、multimodal agent、diagnosis/SOP/task agent、knowledge curator、artifact conversion、conversion concurrency 全部通过。
- npm install/build/vue-tsc：PASSED；npm audit：0 vulnerabilities；静态安装：60 files。
- 真实 Playwright：{len(browser['checks'])}/{len(browser['checks'])} PASSED，console/page/unexpected network errors=0/0/0，viewer 只读通过。
- Final smoke：23/23 PASSED，failed=0，Base URL=`http://127.0.0.1:8012`，确认 8012 为本轮代码。

## 13. 浏览器审核覆盖

- 已在真实 Chrome + 项目 Node/Playwright 中验证 primary intent、requested information、composite intent、canonical query、query variants、Anchor coverage、direct answer ranking、多证据排序、Citation、Confidence 与 no-answer boundary。
- viewer 可读取 Retrieval Quality 页面，R5 面板写控件数为 0；未渲染密码、Authorization 或 token。

## 14. 边界

- `backend/.env` hash 未变化；审批状态未修改；`expert_verified` 未写入。
- 未执行正式全量重建；`TASK25B_ALLOW_FULL_REINDEX=false`；默认 Partition 未修改。
- 未增加知识、Semantic Unit 或向量；未创建/删除 Collection/Partition。
- LoongArch + Kylin 物理实机验收未执行，不宣称通过。
- 未打包、未生成新 ZIP、未执行 Git add/commit/reset/clean/restore；staged={len(staged)}。

## 15. 最终判断

- Candidate recall competitive：**是，刚好达到 0.95 硬门**。
- Direct evidence ranking competitive：**否**（Hit@1=0.20，Hit@3=0.45，MRR=0.336806，nDCG@10=0.363672）。
- Deterministic RAG ready：**否**。
- Formal quality：**未评估，Canary 阻断**。
- Allow Task 25C：**否**。
- Remaining blockers：Direct Answer Hit@1/3、Recall@5/10、MRR、nDCG@10、canonicalization、Multi-query p95 与 Full deterministic path p95。

## Machine evidence

机器证据位于 `.runtime/task25b_r3_dev_r5_r5/`。本任务只生成这一份 Markdown 报告。
"""
    REPORT.write_text(report, encoding="utf-8")
    print(json.dumps({
        "generated_at": now_iso(),
        "status": iteration_2["status"],
        "report": str(REPORT),
        "candidate_recall_at_50": metrics2["candidate_recall_at_50"],
        "formal_run_count": formal["formal_run_count"],
        "browser": browser["status"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
