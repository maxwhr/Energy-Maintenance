from __future__ import annotations

import json
from collections import Counter, defaultdict

from task25b_r1_common import ROOT, RUNTIME, now_iso, sha256_file, write_csv, write_json


SNAPSHOT = RUNTIME / "task25b_v1_frozen_snapshot.json"
REPORT = ROOT / "docs" / "25B_R1_failure_analysis_report.md"
LATENCY_LIMIT_MS = 3500.0


def _rank(items: list[str], expected: set[str]) -> int | None:
    return next((index for index, item in enumerate(items, 1) if str(item) in expected), None)


def _score_for(result: dict, expected: set[str]) -> dict:
    scores = result.get("score_breakdown") or {}
    for expected_id in expected:
        if expected_id in scores:
            return scores[expected_id] or {}
    ranked = result.get("ranked_chunk_ids") or result.get("ranked_document_ids") or result.get("ranked_media_ids") or []
    return (scores.get(str(ranked[0])) or {}) if ranked else {}


def _category_label(category: str) -> str:
    return {
        "device_model_query": "设备型号",
        "fault_code_query": "故障码",
        "fault_symptom_query": "故障现象",
        "manual_section_location": "手册章节",
        "safety_operation_query": "安全操作",
        "image_ocr_query": "OCR",
        "image_visual_descriptor_query": "视觉描述",
        "similar_history_case": "历史案例",
        "no_answer": "无答案",
        "interference_filter": "干扰过滤",
    }.get(category, category)


def main() -> int:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in snapshot["case_results"]:
        grouped[item["case_id"]].append(item)

    rows = []
    failure_counter: Counter[str] = Counter()
    category_counter: dict[str, Counter[str]] = defaultdict(Counter)
    for case_id, results in sorted(grouped.items()):
        by_mode = {item["retrieval_mode"]: item for item in results}
        exemplar = results[0]
        expected = {
            str(item)
            for key in ("expected_chunk_ids", "expected_document_ids", "expected_media_ids")
            for item in (exemplar.get(key) or [])
        }
        lists = {
            mode: [str(value) for key in ("ranked_chunk_ids", "ranked_document_ids", "ranked_media_ids") for value in (item.get(key) or [])]
            for mode, item in by_mode.items()
        }
        keyword = lists.get("keyword", [])
        vector = lists.get("vector", [])
        hybrid = lists.get("hybrid", [])
        final = lists.get("hybrid_rerank", hybrid)
        union = list(dict.fromkeys([*keyword, *vector]))
        keyword_rank = _rank(keyword, expected)
        vector_rank = _rank(vector, expected)
        hybrid_rank = _rank(hybrid, expected)
        final_rank = _rank(final, expected)
        flags: list[str] = []
        if exemplar["category"] == "no_answer":
            if final:
                flags.append("NO_ANSWER_FALSE_POSITIVE")
        else:
            if not _rank(union, expected):
                flags.append("CANDIDATE_MISS")
            if keyword_rank is None:
                flags.append("KEYWORD_CANDIDATE_MISS")
            if vector_rank is None:
                flags.append("VECTOR_CANDIDATE_MISS")
            if exemplar["category"] == "device_model_query" and final_rank != 1:
                flags.append("EXACT_MODEL_NOT_PRIORITIZED")
            if exemplar["category"] == "fault_code_query" and final_rank != 1:
                flags.append("EXACT_FAULT_CODE_NOT_PRIORITIZED")
            if keyword_rank and (final_rank is None or final_rank > keyword_rank):
                flags.append("FUSION_DEGRADATION")
        if hybrid and hybrid == final:
            flags.append("RERANK_NO_OP")
        if float(by_mode.get("vector", {}).get("latency_ms") or 0) > LATENCY_LIMIT_MS:
            flags.append("LATENCY_DASHVECTOR")
        if float(by_mode.get("hybrid_rerank", {}).get("latency_ms") or 0) > LATENCY_LIMIT_MS:
            flags.append("LATENCY_EMBEDDING")
        if not flags:
            flags.append("OTHER")

        priority = [
            "NO_ANSWER_FALSE_POSITIVE", "CANDIDATE_MISS", "KEYWORD_CANDIDATE_MISS", "VECTOR_CANDIDATE_MISS",
            "EXACT_MODEL_NOT_PRIORITIZED", "EXACT_FAULT_CODE_NOT_PRIORITIZED", "FUSION_DEGRADATION",
            "RERANK_NO_OP", "LATENCY_DASHVECTOR", "LATENCY_EMBEDDING", "OTHER",
        ]
        primary = next(item for item in priority if item in flags)
        failure_counter.update(flags)
        category_counter[_category_label(exemplar["category"])].update(flags)
        score = _score_for(by_mode.get("hybrid_rerank", by_mode.get("hybrid", {})), expected)
        recommendation = {
            "CANDIDATE_MISS": "expand calibrated candidate union and validate structured filters",
            "KEYWORD_CANDIDATE_MISS": "improve token expansion and exact field matching",
            "VECTOR_CANDIDATE_MISS": "calibrate similarity and increase candidate depth",
            "EXACT_MODEL_NOT_PRIORITIZED": "apply exact model hard priority",
            "EXACT_FAULT_CODE_NOT_PRIORITIZED": "apply exact fault-code hard priority",
            "FUSION_DEGRADATION": "protect strong keyword rank and threshold vector noise",
            "RERANK_NO_OP": "verify non-zero features and disable reranker if dev gain is absent",
            "LATENCY_DASHVECTOR": "reuse clients, warm cache and apply vector timeout fallback",
            "LATENCY_EMBEDDING": "cache query embedding and parallelize independent retrieval",
            "NO_ANSWER_FALSE_POSITIVE": "add abstention threshold and evidence margin checks",
            "OTHER": "retain as regression evidence",
        }[primary]
        rows.append({
            "case_id": case_id,
            "category": _category_label(exemplar["category"]),
            "query_hash": exemplar["query_sha256"],
            "expected_ids": sorted(expected),
            "keyword_candidates": keyword,
            "vector_candidates": vector,
            "hybrid_candidates": hybrid,
            "final_candidates": final,
            "first_relevant_rank": final_rank,
            "candidate_recall": float(bool(_rank(union, expected))) if expected else float(not final),
            "exact_model_match": None if exemplar["category"] != "device_model_query" else final_rank == 1,
            "exact_fault_code_match": None if exemplar["category"] != "fault_code_query" else final_rank == 1,
            "raw_vector_score": score.get("vector_raw_score"),
            "normalized_vector_score": score.get("vector_score"),
            "rrf_score": score.get("rrf_score"),
            "rerank_score": score.get("rerank_score"),
            "final_score": score.get("final_score"),
            "latency_breakdown": {mode: item.get("latency_ms") for mode, item in by_mode.items()},
            "failure_category": primary,
            "failure_flags": flags,
            "recommended_action": recommendation,
        })

    payload = {
        "status": "COMPLETED",
        "generated_at": now_iso(),
        "source_snapshot_sha256": sha256_file(SNAPSHOT),
        "test_v1_usage": "error_analysis_and_regression_only",
        "case_count": len(rows),
        "failure_counts": dict(sorted(failure_counter.items())),
        "by_category": {name: dict(sorted(counts.items())) for name, counts in sorted(category_counter.items())},
        "cases": rows,
    }
    json_path = write_json("failure_analysis.json", payload)
    fields = [
        "case_id", "category", "query_hash", "expected_ids", "keyword_candidates", "vector_candidates",
        "hybrid_candidates", "final_candidates", "first_relevant_rank", "candidate_recall",
        "exact_model_match", "exact_fault_code_match", "raw_vector_score", "normalized_vector_score",
        "rrf_score", "rerank_score", "final_score", "latency_breakdown", "failure_category",
        "failure_flags", "recommended_action",
    ]
    csv_path = write_csv("failure_analysis.csv", fields, rows)

    lines = [
        "# Task 25B-R1 Failure Analysis Report", "",
        "> test_v1 已暴露，只用于误差分析和防回归，不再作为独立盲测集。", "",
        "## Scope", "",
        f"- Cases analyzed: {len(rows)}",
        f"- Source snapshot SHA-256: `{payload['source_snapshot_sha256']}`",
        f"- JSON: `{json_path.relative_to(ROOT)}`",
        f"- CSV: `{csv_path.relative_to(ROOT)}`", "",
        "## Failure classes", "",
        "| Class | Count |", "|---|---:|",
        *[f"| {name} | {count} |" for name, count in sorted(failure_counter.items())], "",
        "## Category summary", "",
        "| Category | Primary observations |", "|---|---|",
        *[f"| {name} | " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) + " |" for name, counts in sorted(category_counter.items())], "",
        "## Root causes", "",
        "1. Vector candidates were admitted without a dev-calibrated usefulness threshold and could demote stronger keyword evidence.",
        "2. The original feature reranker frequently preserved the hybrid ordering, so its existence did not demonstrate ranking gain.",
        "3. Exact device-model and fault-code evidence needs hard priority before soft semantic fusion.",
        "4. External embedding and DashVector calls dominated latency; warm reuse, bounded caching and timeout fallback are required.",
        "5. No-answer cases need explicit abstention metrics rather than being treated as ordinary empty relevance lists.", "",
        "## Integrity", "",
        "No test_v2 labels were created or inspected during this analysis.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "sha256": sha256_file(REPORT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
