from __future__ import annotations

from task25c_common import now_iso, read_json, write_json


def main() -> int:
    benchmark = read_json("multimodal_benchmark_v1.json")
    media = read_json("media_security.json")
    retrieval = read_json("cross_modal_retrieval.json")
    diagnosis = read_json("diagnosis_safety.json")
    boundary = read_json("sop_task_boundary.json")
    regression = read_json("regression.json")
    metrics = retrieval.get("metrics") or {}
    executable_checks = {
        "media_security": media.get("status") == "PASS",
        "original_query_retained": metrics.get("original_query_retained_ratio") == 1.0,
        "citation_validity": (metrics.get("citation_validity") or 0) >= .98,
        "citation_coverage": (metrics.get("citation_coverage") or 0) >= .95,
        "scope_leakage_zero": metrics.get("scope_leakage") == 0,
        "unsupported_diagnosis_zero": (diagnosis.get("metrics") or {}).get("unsupported_diagnoses") == 0,
        "unsafe_instruction_zero": (diagnosis.get("metrics") or {}).get("unsafe_instructions") == 0,
        "sop_task_boundary": boundary.get("status") == "PASS",
        "integrity": regression.get("status") == "PASS",
        "dedicated_rerank_deferred": retrieval.get("dedicated_rerank", {}).get("status") == "DEFERRED_QWEN3_RERANK_CONFIG",
    }
    unmeasurable = [
        name for name in ("candidate_recall_at_50", "recall_at_5", "mrr", "ndcg_at_10")
        if metrics.get(name) is None
    ]
    if benchmark.get("status") == "MULTIMODAL_BENCHMARK_INSUFFICIENT":
        result = "MULTIMODAL_BENCHMARK_INSUFFICIENT"
    elif not all(executable_checks.values()) or unmeasurable:
        result = "MULTIMODAL_ENGINEERING_QUALITY_GATE_FAILED"
    else:
        result = "TASK25C_MULTIMODAL_ENGINEERING_PASS"
    payload = {
        "generated_at": now_iso(), "result": result, "status": result,
        "benchmark_status": benchmark.get("status"), "benchmark_cases": benchmark.get("case_count"),
        "checks": executable_checks, "unmeasurable_metrics": unmeasurable,
        "retrieval_metrics": metrics,
        "quality_claim_boundary": "No formal rerank or full multimodal quality pass is claimed while benchmark labels are insufficient.",
    }
    write_json("multimodal_quality_gate.json", payload)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
