from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".runtime" / "task25b_r3_dev_r5_r4_mm"
REPORT = ROOT / "docs" / "25B_R3_DEV_R5_R4_MM_deterministic_query_understanding_report.md"
FINAL_STATUS = "QUERY_AWARE_GROUNDED_RAG_R4_QUALITY_GATE_FAILED"


def read_json(name: str) -> dict[str, Any]:
    path = RUNTIME / name
    if not path.is_file():
        raise FileNotFoundError(f"required evidence is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def percent(value: float | None) -> str:
    return "NOT EMITTED" if value is None else f"{value * 100:.2f}%"


def milliseconds(value: float | None) -> str:
    return "NOT EMITTED" if value is None else f"{value:.3f} ms"


def failed_gates(checks: dict[str, Any]) -> list[str]:
    return [name for name, passed in checks.items() if passed is False]


def failure_category_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        failed = False
        if not row.get("no_answer") and not row.get("candidate_hit_at_50"):
            counts["candidate_miss"] += 1
            failed = True
        if row.get("expected_intent") != row.get("actual_intent"):
            counts["intent"] += 1
            failed = True
        if row.get("canonical_correct") is False:
            counts["canonicalization"] += 1
            failed = True
        if bool(row.get("requires_clarification")) != bool(row.get("clarified")):
            counts["clarification"] += 1
            failed = True
        if row.get("context_correct") is False:
            counts["context_merge"] += 1
            failed = True
        if row.get("hallucinated_models"):
            counts["hallucinated_model"] += 1
            failed = True
        if row.get("hallucinated_alarms"):
            counts["hallucinated_alarm"] += 1
            failed = True
        if row.get("scope_valid") is False:
            counts["scope_leakage"] += 1
            failed = True
        if row.get("error"):
            counts["error"] += 1
            failed = True
        if failed:
            counts["cases_with_observed_failure"] += 1
    return dict(sorted(counts.items()))


def main() -> None:
    snapshot = read_json("r5_r3_snapshot.json")
    labels = read_json("label_integrity.json")
    deterministic_probe = read_json("deterministic_probe.json")
    ambiguity_probe = read_json("ambiguity_options_probe.json")
    minimax_probe = read_json("minimax_ambiguity_probe.json")
    resume = read_json("resume_state.json")
    iteration_1 = read_json("canary_iteration_1.json")
    tuning = read_json("dev_tuning.json")
    iteration_2 = read_json("canary_iteration_2.json")
    vector = read_json("vector_reconciliation.json")
    regression = read_json("regression_summary.json")

    det1 = iteration_1["deterministic_only"]
    opt1 = iteration_1["optional_minimax"]
    det2 = iteration_2["deterministic_only"]
    opt2 = iteration_2["optional_minimax"]
    metrics = det2["metrics"]
    latency = det2["latency"]
    optional_component = opt2["component"]
    counts = vector["partition_counts"]
    browser = regression["browser"]
    smoke = regression["final_smoke"]

    if snapshot.get("source_result") != "QUERY_UNDERSTANDING_CONTRACT_NOT_READY":
        raise RuntimeError("the frozen R5-R3-MM source result changed")
    if labels.get("source_unchanged") is not True or labels.get("minimax_output_used") is not False:
        raise RuntimeError("label-audit boundary is not intact")
    if resume.get("completed_prerequisites_reexecuted") is not False:
        raise RuntimeError("completed prerequisites were unexpectedly re-executed")
    if iteration_2.get("status") != FINAL_STATUS or iteration_2.get("passed") is not False:
        raise RuntimeError("iteration 2 is not in the expected failed-gate state")
    if iteration_2.get("actual_result_count") != 152 or iteration_2.get("missing_result_count") != 0:
        raise RuntimeError("iteration 2 result set is incomplete")
    if iteration_2.get("duplicate_result_count") != 0:
        raise RuntimeError("iteration 2 contains duplicate results")
    if any((RUNTIME / name).exists() for name in ("formal_test.json", "formal_test_frozen.json", "formal_quality_gate.json")):
        raise RuntimeError("formal-test evidence exists even though deterministic Canary failed")
    if vector.get("passed") is not True or vector.get("read_only") is not True:
        raise RuntimeError("vector reconciliation did not remain read-only")
    if vector.get("re_embedded") != 0 or vector.get("re_upserted") != 0:
        raise RuntimeError("vector mutations were detected")
    if smoke.get("status") != "PASSED" or smoke.get("failed") != 0:
        raise RuntimeError("final smoke evidence is incomplete")
    if browser.get("status") != "NOT_EXECUTED_TOOL_BOOTSTRAP_BLOCKED":
        raise RuntimeError("browser status must explicitly record the tooling blocker")
    if regression["boundaries"].get("backend_env_changed") is not False:
        raise RuntimeError("backend/.env boundary changed")
    if regression["boundaries"].get("staged_files") != 0:
        raise RuntimeError("staged files were detected")

    revised_rows = [row for row in labels["audit_rows"] if row.get("changed")]
    revised_lines = "\n".join(
        f"- `{row['case_id']}`：`{row['old']['intent']}`/clarify={str(row['old']['clarify']).lower()} → "
        f"`{row['new']['intent']}`/clarify={str(row['new']['clarify']).lower()}。证据：{row['evidence']}"
        for row in revised_rows
    )
    det1_failed = failed_gates(det1["checks"])
    det2_failed = failed_gates(det2["checks"])
    failure_distribution = failure_category_distribution(det2["rows"])
    opt_gain = optional_component["quality_gain"]
    regression_security = regression["security"]
    frontend = regression["frontend"]
    pytest = regression["pytest"]

    report = f"""# Task 25B-R3-DEV-R5-R4-MM 确定性查询理解统一报告

最终状态：`{FINAL_STATUS}`

结论先行：确定性 Query-Aware RAG 在一次 Train/Dev 校准后明显改善，并满足引用、无答案、安全、错误率和全部性能门，但 iteration 2 仍未达到 Candidate Recall@50、MRR、nDCG@10 和 intent accuracy 四个硬门。因此 Formal 测试集没有创建、冻结或运行；当前不得进入 Task 25C。MiniMax 仅作为可选歧义裁决器，Canary 中未带来检索质量增益，且 structured success 与 p95 也未达到可选组件目标。安全降级对两个失败案例保持 100% 无损。

## 1. Codex 容量中断与恢复

- 中断原因为 Codex 所选模型容量不足（`Selected model is at capacity`），不是项目代码、MiniMax、DashVector、Embedding、PostgreSQL、前端或确定性查询理解故障。
- 恢复分类：`{resume.get('classification')}`。原 iteration 1 进程已结束，完整 artifact 被保留；没有启动重复 iteration 1 run，也没有重复执行已成功 case/config。
- 原 artifact 每配置 81 条，而恢复指令声明 76 条。该差异被记录为不可变现场证据：iteration 1 共 162 条、missing=0、duplicate=0；iteration 2 使用校准后的 76 条执行集，共 152 条。
- Snapshot、30 条标签审计、55 条确定性 Probe、20 条歧义候选 Probe、20 次真实 MiniMax Probe 均未重跑。
- iteration 2 使用 `(iteration, configuration, case_id)` 唯一键、进程锁、逐案例原子 checkpoint 和 `--only-missing` 恢复；checkpoint 最终同时保留 iteration 1 的 162 条与 iteration 2 的 152 条唯一记录。

## 2. R5-R3-MM 冻结基线

- 来源：`{snapshot.get('source')}`；状态：`{snapshot.get('source_result')}`；运行时选择：`{snapshot.get('selected_runtime_model')}`。
- R5-R3-MM MiniMax-M3 structured={percent(snapshot['model_ab']['MiniMax-M3']['structured_success_ratio'])}，intent={percent(snapshot['model_ab']['MiniMax-M3']['intent_accuracy'])}，canonicalization={percent(snapshot['model_ab']['MiniMax-M3']['canonicalization_accuracy'])}，p95={milliseconds(snapshot['model_ab']['MiniMax-M3']['p95_ms'])}。
- MiniMax-M2.7-highspeed structured={percent(snapshot['model_ab']['MiniMax-M2.7-highspeed']['structured_success_ratio'])}，p95={milliseconds(snapshot['model_ab']['MiniMax-M2.7-highspeed']['p95_ms'])}。
- 受保护的 R5-R3-MM 报告与机器 artifact SHA-256 均未变化。

## 3. A/B 标签独立审计

- 审计 30 条，唯一 case ID 校验通过；修订 3 条：`ab16`、`ab19`、`ab27`。
- 审计依据为 `human_rule_audit_only`；没有使用 MiniMax 输出，没有使用正式测试标签，旧标签源文件 SHA-256 前后一致。

{revised_lines}

## 4. 确定性查询理解与 canonicalization

- 实现系统侧信号提取、意图识别、canonicalization、型号/告警/数字/条件保留和会话补充合并。
- Fast Path 继续兼容：显式 `retrieval_mode=fast` 不启用扩展查询理解，避免改变既有 API 语义。
- Probe：{deterministic_probe['metrics']['cases']} 条；intent={percent(deterministic_probe['metrics']['intent_accuracy'])}；canonicalization={percent(deterministic_probe['metrics']['canonicalization_accuracy'])}；clarification={percent(deterministic_probe['metrics']['clarification_accuracy'])}。
- 型号/告警幻觉={deterministic_probe['metrics']['hallucinated_models']}/{deterministic_probe['metrics']['hallucinated_alarms']}；外部调用={deterministic_probe['metrics']['external_calls']}；p95={milliseconds(deterministic_probe['metrics']['p95_ms'])}。

## 5. 歧义候选与追问模板

- Ambiguity Options Probe：{ambiguity_probe['metrics']['cases']} 条，正确解释覆盖={percent(ambiguity_probe['metrics']['correct_interpretation_coverage'])}，最大候选数={ambiguity_probe['metrics']['max_candidates']}。
- 知识答案泄漏={ambiguity_probe['metrics']['knowledge_answer_leakage']}；expected label 泄漏={ambiguity_probe['metrics']['expected_label_leakage']}。
- 追问由确定性模板生成；MiniMax 不生成检索查询、维修答案、型号或告警码。

## 6. MiniMax 歧义裁决 Probe

- 真实 MiniMax-M3 调用 {minimax_probe['metrics']['real_calls']} 次，structured success={minimax_probe['metrics']['structured_success']}/{minimax_probe['metrics']['real_calls']}（{percent(minimax_probe['metrics']['structured_success_ratio'])}），唯一失败安全回退。
- unknown interpretation IDs={minimax_probe['metrics']['unknown_interpretation_ids']}；型号/告警幻觉={minimax_probe['metrics']['hallucinated_models']}/{minimax_probe['metrics']['hallucinated_alarms']}；失败安全降级={percent(minimax_probe['metrics']['failure_safe_fallback_ratio'])}；p95={milliseconds(minimax_probe['metrics']['p95_ms'])}。
- 该 Probe 达到可选组件目标，但其结果不替代端到端 Canary，也没有被用于修改标签。

## 7. Canary iteration 1

- 数据集：`{iteration_1.get('dataset_version')}`；不可变 artifact 为 81 条/配置、2 个配置、162 条结果；missing=0，duplicate=0。
- 由于 predecessor artifact 与恢复指令的 76 条口径不一致，现场分类为 `CANARY_STATE_INCONSISTENT`，但 artifact 本身唯一且完整，因此未重跑。
- deterministic-only 状态：`{iteration_1.get('status')}`；失败门：{', '.join(det1_failed)}。
- 核心指标：Candidate R@50={percent(det1['metrics']['candidate_recall_at_50'])}，R@5={percent(det1['metrics']['recall_at_5'])}，R@10={percent(det1['metrics']['recall_at_10'])}，MRR={det1['metrics']['mrr']:.6f}，nDCG@10={det1['metrics']['ndcg_at_10']:.6f}，intent={percent(det1['metrics']['intent_accuracy'])}，canonicalization={percent(det1['metrics']['canonicalization_accuracy'])}，clarification precision={percent(det1['metrics']['clarification_precision'])}，context merge={percent(det1['metrics']['context_merge_accuracy'])}，告警幻觉={det1['metrics']['hallucinated_alarms']}。
- optional MiniMax 端到端指标与 deterministic-only 相同，quality gain 全为 0。

## 8. 唯一一次 Train/Dev 校准

- 执行次数：{tuning.get('calibration_count')}；状态：`{tuning.get('status')}`。
- 标签修改={tuning.get('labels_changed')}；rerank weights 修改={tuning.get('rerank_weights_changed')}；confidence/quality gate 阈值修改={tuning.get('confidence_thresholds_changed')}/{tuning.get('quality_gate_thresholds_changed')}。
- 通用修改：外层请求短语优先；补充口语 action/procedure 词表；RS232/RS485 不再误识别为告警码；具体会话症状可解除通用缺失症状；alarm names/numbers 纳入会话槽位。
- 执行集从 81 调整为 76，仅去除 5 条重复 no-answer；仍保留 8 条 no-answer（3 条原始 + 5 条实体冲突）。没有使用正式测试数据，没有增加语料或重新索引。
- 向量变化：re-embedded={tuning['vector_mutations']['re_embedded']}，re-upserted={tuning['vector_mutations']['re_upserted']}，collection/partition changes={tuning['vector_mutations']['collection_changes']}/{tuning['vector_mutations']['partition_changes']}。

## 9. Canary iteration 2 与确定性质量门

- 数据集：`{iteration_2.get('dataset_version')}`；run ID：`{iteration_2.get('run_id')}`；76 条/配置，expected/actual={iteration_2.get('expected_result_count')}/{iteration_2.get('actual_result_count')}，missing={iteration_2.get('missing_result_count')}，duplicate={iteration_2.get('duplicate_result_count')}。
- deterministic-only 状态：`{iteration_2.get('status')}`；失败门：{', '.join(det2_failed)}。
- 失败案例观测分布：`{json.dumps(failure_distribution, ensure_ascii=False, sort_keys=True)}`。该分布是逐案例可观测错误分类，不替代总体门禁。

| 指标 | iteration 2 | 硬门 | 结果 |
|---|---:|---:|---|
| Candidate Recall@50 | {percent(metrics['candidate_recall_at_50'])} | >=95% | FAIL |
| Recall@5 | {percent(metrics['recall_at_5'])} | >=80% | PASS |
| Recall@10 | {percent(metrics['recall_at_10'])} | >=85% | PASS |
| MRR | {metrics['mrr']:.6f} | >=0.75 | FAIL |
| nDCG@10 | {metrics['ndcg_at_10']:.6f} | >=0.80 | FAIL |
| Citation validity | {percent(metrics['citation_validity'])} | >=98% | PASS |
| Citation coverage | {percent(metrics['citation_coverage'])} | >=95% | PASS |
| No-answer F1 | {percent(metrics['no_answer_f1'])} | >=85% | PASS |
| Intent accuracy | {percent(metrics['intent_accuracy'])} | >=95% | FAIL |
| Canonicalization | {percent(metrics['canonicalization_accuracy'])} | >=90% | PASS |
| Clarification precision/recall | {percent(metrics['clarification_precision'])} / {percent(metrics['clarification_recall'])} | >=85% / >=85% | PASS |
| Context merge | {percent(metrics['context_merge_accuracy'])} | >=95% | PASS |
| 型号/告警幻觉 | {metrics['hallucinated_models']} / {metrics['hallucinated_alarms']} | 0 / 0 | PASS |
| Scope leakage | {metrics['scope_leakage']} | 0 | PASS |
| Error rate | {percent(metrics['error_rate'])} | 0% | PASS |

性能全部通过：Fast Path p95={milliseconds(latency['fast_path_p95_ms'])}，Deterministic Understanding p95={milliseconds(latency['deterministic_understanding_p95_ms'])}，Multi-query p95={milliseconds(latency['multi_query_p95_ms'])}，Full deterministic path p95={milliseconds(latency['full_deterministic_path_p95_ms'])}。

## 10. Optional MiniMax Canary

- eligible/called：Canary component 记录 attempted={optional_component['attempted']}；本执行中所有 eligible 调用均计入 attempted，因此 called={optional_component['attempted']}。
- structured success={optional_component['structured_success']}/{optional_component['attempted']}（{percent(optional_component['structured_success_ratio'])}），fallback={optional_component['fallback_cases']}，p95={milliseconds(optional_component['p95_ms'])}。
- 失败后 deterministic preservation={percent(optional_component['failure_lossless_ratio'])}；SLO={optional_component['slo_passed']}。
- ambiguity accuracy 没有作为独立 Canary 字段发出，不能伪报；前置 Ambiguity Probe 的正确解释覆盖为 {percent(ambiguity_probe['metrics']['correct_interpretation_coverage'])}。
- quality gain：Candidate R@50={opt_gain['candidate_recall_at_50']:+.6f}，R@5={opt_gain['recall_at_5']:+.6f}，MRR={opt_gain['mrr']:+.6f}，clarification P/R={opt_gain['clarification_precision']:+.6f}/{opt_gain['clarification_recall']:+.6f}。结论：没有增益，也没有退化。
- 可选组件 structured 目标 >=95% 未通过（83.33%）；p95 <=5000ms 未通过（5013.361ms）。

## 11. Formal 测试

- deterministic-only Canary 未通过，所以没有创建、冻结或运行 `task25b_r3_dev_r5_r4_mm_zh_v1`。
- created=false；frozen=false；SHA-256=NOT CREATED；official run count=0；正式结果未用于调参。
- Formal 脚本仅实现前置门禁，未执行；API 显示 `NOT_CREATED_DETERMINISTIC_CANARY_FAILED`。

## 12. 向量只读对账

- Collection：`{vector.get('collection')}`；状态：`{vector.get('status')}`；read-only={vector.get('read_only')}。
- pilot_r2={counts.get('pilot_r2')}；pilot_r3_semantic={counts.get('pilot_r3_semantic')}；pilot_r4_grounded={counts.get('pilot_r4_grounded')}；pilot_r5_query_aware={counts.get('pilot_r5_query_aware')}。
- re-embedded/re-upserted={vector.get('re_embedded')}/{vector.get('re_upserted')}；missing/orphan/duplicate/mismatch={vector.get('missing')}/{vector.get('orphan')}/{vector.get('duplicate')}/{vector.get('mismatch')}。
- 默认 Partition affected={vector.get('default_partition_affected')}；Collection/Partition 未创建、删除或修改；正式全量重建未执行。

## 13. 完整回归

- compileall：`{regression['compileall']['status']}`（app/scripts/tests）。
- Alembic heads/current：`{regression['alembic']['heads']}` / `{regression['alembic']['current']}`。
- pytest：{pytest['passed']} passed，{pytest['skipped']} skipped，{pytest['warnings']} warnings，failed={pytest['failed']}。
- Security：config `{regression_security['config']}`；secret scan `{regression_security['secret_scan']}`（findings={regression_security['secret_scan_findings']}，blocking={regression_security['secret_scan_blocking']}）；log `{regression_security['log_sanitization']}`；upload {regression_security['upload_security_cases']}/{regression_security['upload_security_cases']}；RBAC {regression_security['rbac_cases']}/{regression_security['rbac_cases']}。
- 业务流：DashVector hybrid 使用 fake-in-memory 且无真实向量写；multimodal evidence、multimodal agent、diagnosis/SOP/task agent、curator、artifact conversion 和 concurrency 全部通过。
- npm install `{frontend['npm_install']}`；npm audit vulnerabilities={frontend['npm_audit_vulnerabilities']}；build `{frontend['build']}`；vue-tsc `{frontend['vue_tsc']}`；static install `{frontend['static_install']}`，复制 {frontend['static_files_copied']} 个文件。

## 14. 前端、浏览器与 Final Smoke

- Retrieval Quality 页面已增加只读 R5-R4-MM 面板，展示 deterministic-first、MiniMax optional、Probe、Canary、Formal 和向量状态；后端受 RBAC 保护的 summary API 已返回最新状态。
- 真实浏览器审核：`{browser['status']}`。所要求的应用内浏览器运行时初始化失败：`Cannot redefine property: process`。因此浏览器 gate 脚本未执行、未生成 browser evidence，console/page/network 三项不能声称为 0；没有伪造页面审核结论。
- Final Smoke：`{smoke['status']}`，base URL `{smoke['base_url']}`，{smoke['total']} checks，failed={smoke['failed']}；默认跳过会新增 qa_records 的 retrieval write。

## 15. 边界与未执行项

- `backend/.env` SHA-256 与冻结值一致，changed=false；未打印 Key、Authorization、完整 prompt 或完整模型响应。
- engineering approval changed=false；expert_verified written=false；正式全量重建=false；默认 Partition 未修改。
- LoongArch + Kylin 未进行物理实机验收，不能声称通过。
- 未创建新 ZIP；既有 3 个 ZIP 的 hash/size 不变；delivery、delivery_staging 与 docs.zip 未更新。
- staged files=0；未执行 git add/commit/reset/clean/restore；保留全部现有工作区更改。

## 16. 最终判断

- deterministic RAG ready：**否**，iteration 2 仍有 4 个硬门失败。
- optional MiniMax usable：**仅可继续作为安全可降级的实验组件，当前未达到 Canary SLO**。
- graceful degradation：**通过，100% 无损**。
- Formal quality：**未评估，正式集未创建且 official run count=0**。
- allow Task 25C：**否**。
- remaining blockers：Candidate Recall@50、MRR、nDCG@10、intent accuracy，以及真实浏览器审核工具链阻塞。

## Machine evidence

机器证据位于 `.runtime/task25b_r3_dev_r5_r4_mm/`。本任务只生成本 Markdown 报告，不生成其他恢复报告。
"""
    REPORT.write_text(report, encoding="utf-8")
    print(json.dumps({"status": "GENERATED", "result": FINAL_STATUS, "report": str(REPORT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
