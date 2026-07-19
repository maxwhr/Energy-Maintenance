from __future__ import annotations

import csv
import json
from collections import Counter

from task25b_r3_dev_r2_common import OUT, ROOT, now_iso


def main() -> None:
    source = OUT / "v2_relevance_cardinality.csv"
    if not source.exists():
        raise SystemExit("run v2 forensics before metric-contract audit")
    with source.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    relevant = [int(row["expected_chunk_count"] or 0) for row in rows]
    single = sum(value == 1 for value in relevant)
    multi = sum(value > 1 for value in relevant)
    impossible = sum(value < 3 for value in relevant)
    achievable = len(rows) - impossible
    audit = {
        "generated_at": now_iso(), "source": str(source.relative_to(ROOT)), "cases": len(rows),
        "metric_level": "chunk", "fixed_return_k": 5, "single_relevant_cases": single,
        "multi_relevant_cases": multi, "impossible_precision_at_5_cases": impossible,
        "precision_at_5_gate_achievable_cases": achievable,
        "precision_at_5_gate_mathematically_applicable": achievable == len(rows),
        "rules": {
            "single_relevant": ["Hit@1", "Hit@5", "MRR", "nDCG@10", "document/section accuracy"],
            "multi_relevant": ["Precision@5", "R-Precision", "Recall@5", "MAP", "nDCG@10"],
            "surfaced": ["surfaced_precision", "surfaced_recall", "returned_result_count", "irrelevant_result_rate"],
        },
        "cardinality_distribution": dict(sorted(Counter(relevant).items())),
        "raw_precision_at_5_retained": True,
        "quality_gate_contract_corrected": True,
        "reason": "A fixed five-result precision denominator cannot reach 0.45 when fewer than three relevant chunks are labelled.",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "metric_contract_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = ROOT / "docs" / "25B_R3_DEV_R2_metric_contract_report.md"
    report.write_text(
        "# Task 25B-R3-DEV-R2 指标契约审计\n\n"
        f"- test_v2 cases: {len(rows)}\n- 单相关项: {single}\n- 多相关项: {multi}\n"
        f"- 固定 Top-5 下 P@5 < 0.45 数学不可达的 case: {impossible}\n"
        "- raw Precision@5 保留为描述性指标；单相关项使用 Hit/MRR/章节与文档准确率，多相关项使用 Precision@5/R-Precision/Recall@5。\n"
        "- 本审计未修改 v2、标签或质量阈值。\n", encoding="utf-8")
    print(json.dumps({"status": "PASSED", "cases": len(rows), "impossible_precision_cases": impossible, "metric_gate_corrected": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
