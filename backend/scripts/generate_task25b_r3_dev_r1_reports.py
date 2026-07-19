from __future__ import annotations

import json
from pathlib import Path

from task25b_r3_dev_common import ROOT, now_iso


OUT = ROOT / ".runtime" / "task25b_r3_dev_r1"


def read(name: str) -> dict:
    path = OUT / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def report(name: str, title: str, body: str) -> None:
    (ROOT / "docs" / name).write_text(f"# {title}\n\n{body.strip()}\n", encoding="utf-8")


def main() -> None:
    forensic = read("failed_run_snapshot.json"); labels = read("benchmark_label_integrity.json")
    dataset = read("dataset_v2_manifest.json"); scope = read("scope_contract.json")
    keyword = read("keyword_path.json"); fields = read("model_alarm_fields.json")
    canary = read("canary_result.json"); quality = read("quality_gate_v2.json")
    recon = read("pilot_reconciliation.json"); tuning = read("dev_tuning_snapshot.json")
    common = (
        f"生成时间：{now_iso()}\n\n"
        f"失败 v1 run `{forensic.get('run_id')}` 已只读冻结并保留，不得覆盖。"
        f"新数据集 `{dataset.get('dataset_version')}` 与 v1 隔离，train/dev/test_v2={dataset.get('splits')}。"
        f"Canary=`{canary.get('status')}`；唯一正式 v2 run `{quality.get('run_id')}` 的质量门结果为 "
        f"`{quality.get('result')}`。审批仍为开发工程审批，`expert_verified=false`。"
        "本任务未重新索引 1,262 个向量，未修改 default Partition，未执行正式全量重建；LoongArch 未实机验收，不打包、不提交 Git。"
    )
    report("25B_R3_DEV_R1_retrieval_scope_remediation_report.md", "Task 25B-R3-DEV-R1 检索作用域治理报告",
           common + f"\n\n## Scope\n\n```json\n{json.dumps(scope,ensure_ascii=False,indent=2)}\n```\n\n"
           "Keyword、Vector、Hybrid、Adaptive 及 fallback 均使用同一不可变 Scope；未知语言、英文备用、测试资料、营销资料和 superseded 资料在候选 SQL/PG 回查阶段排除。")
    report("25B_R3_DEV_R1_benchmark_label_integrity_report.md", "Task 25B-R3-DEV-R1 Benchmark 标签完整性报告",
           common + f"\n\n- v1 cases：{labels.get('total_cases')}\n- 分类：`{json.dumps(labels.get('classification_counts',{}),ensure_ascii=False)}`\n"
           f"- stale expected IDs：{len(read('stale_expected_ids.json').get('items',[]))}\n"
           f"- v2 SHA-256：`{dataset.get('dataset_sha256')}`\n- 标签修正：`{json.dumps(dataset.get('corrections',{}),ensure_ascii=False)}`\n"
           "- v1 未修改；所有修正只存在于 v2。")
    report("25B_R3_DEV_R1_chinese_keyword_report.md", "Task 25B-R3-DEV-R1 中文关键词检索报告",
           common + f"\n\n- Recall@5：{keyword.get('recall_at_5')}\n- MRR：{keyword.get('mrr')}\n"
           f"- citation validity：{keyword.get('citation_validity')}\n- p50/p95：{keyword.get('p50_ms')}/{keyword.get('p95_ms')} ms\n"
           f"- 外部 API 调用：{keyword.get('external_api_call_count')}\n- Embedding/DashVector 违规：{keyword.get('embedding_violation_count')}/{keyword.get('dashvector_violation_count')}\n")
    report("25B_R3_DEV_R1_adaptive_scope_report.md", "Task 25B-R3-DEV-R1 Adaptive Scope 报告",
           common + "\n\nAdaptive 路由、exact model/alarm、semantic hybrid 和 timeout fallback 均保留 `chinese_engineering_pilot_r2`。\n\n"
           f"Canary 分模式：\n```json\n{json.dumps(canary.get('by_mode',{}),ensure_ascii=False,indent=2)}\n```\n")
    report("25B_R3_DEV_R1_latency_report.md", "Task 25B-R3-DEV-R1 检索延迟报告",
           common + f"\n\n## Dev 调优\n\n```json\n{json.dumps(tuning,ensure_ascii=False,indent=2)}\n```\n\n"
           f"## 正式 v2\n\n```json\n{json.dumps({k:{x:y for x,y in v.items() if x in {'p50_ms','p95_ms','p99_ms','timeout_rate','error_rate'}} for k,v in quality.get('by_mode',{}).items()},ensure_ascii=False,indent=2)}\n```\n")
    report("25B_R3_DEV_R1_canary_report.md", "Task 25B-R3-DEV-R1 Canary 报告",
           common + f"\n\n- 最终状态：`{canary.get('status')}`\n- cases/modes：{canary.get('case_count')}/{canary.get('modes')}\n"
           f"- 检查：`{json.dumps(canary.get('checks',{}),ensure_ascii=False)}`\n- 前四轮失败证据保留为 canary_attempt_1..4.json。\n")
    report("25B_R3_DEV_R1_quality_gate_v2_report.md", "Task 25B-R3-DEV-R1 v2 质量门报告",
           common + f"\n\n- test_v2 cases/results：{quality.get('cases')}/{quality.get('results')}\n"
           f"- checks：`{json.dumps(quality.get('checks',{}),ensure_ascii=False)}`\n\n"
           f"```json\n{json.dumps(quality.get('by_mode',{}),ensure_ascii=False,indent=2)}\n```\n\n"
           "未通过项不得通过降阈值、删除 case 或覆盖 run 处理。")
    marker = "<!-- TASK25B_R3_DEV_R1_BEGIN -->"
    addition = (
        f"\n\n{marker}\n## Task 25B-R3-DEV-R1 检索治理更新\n\n"
        f"- v1 run `{forensic.get('run_id')}` 失败且保留；v2 run `{quality.get('run_id')}` 独立保存。\n"
        f"- Benchmark 数据集状态：`BENCHMARK_DATASET_READY`；质量门状态：`QUALITY_GATE_FAILED`，二者不得混淆。\n"
        f"- Scope：`chinese_engineering_pilot_r2`；Canary：`{canary.get('status')}`；正式 v2：`{quality.get('result')}`。\n"
        f"- Pilot 对账：{recon.get('remote_partition_count')}/{recon.get('eligible')}，re-embedded=0、re-upserted=0。\n"
        "- 工程审批不等于专家验证；正式全量重建未执行；不打包、不提交 Git。\n"
        "<!-- TASK25B_R3_DEV_R1_END -->\n"
    )
    updates = [
        "docs/25B_R2_U3_R3_DEV_chinese_engineering_benchmark_report.md",
        "docs/25B_R2_U3_R3_DEV_chinese_knowledge_governance_report.md",
        "docs/25B_R2_U3_R3_DEV_chinese_pilot_index_report.md", "docs/25B_R2_full_reindex_go_no_go_report.md",
        "docs/09_testing_acceptance_and_quality_spec.md", "docs/12_functional_design_specification.md",
        "docs/19_delivery_checklist.md", "README.md", "backend/README.md",
    ]
    for rel in updates:
        path = ROOT / rel; text = path.read_text(encoding="utf-8") if path.exists() else ""
        if marker not in text:
            path.write_text(text.rstrip() + addition, encoding="utf-8")
    print(json.dumps({"status": "PASSED", "reports": 7, "updated": len(updates)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
