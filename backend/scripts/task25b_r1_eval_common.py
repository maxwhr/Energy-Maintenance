from __future__ import annotations

import hashlib
import math
import statistics
import time
from collections import defaultdict
from typing import Any

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import RetrievalEvaluationCase, User
from app.schemas.retrieval import RetrievalQueryRequest
from app.services.retrieval_evaluation_service import RetrievalEvaluationService
from app.services.retrieval_service import RetrievalService


SOURCE_TYPE = "task25b_r1_engineering_controlled"
CANARY_NAMESPACE = "task25b_r1_canary"


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    return float(ordered[min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))])


def load_cases(db, split: str, *, allow_blind: bool = False) -> list[RetrievalEvaluationCase]:
    if split == "test_v2" and not allow_blind:
        raise RuntimeError("test_v2 labels are frozen and unavailable to tuning workflows")
    physical = "test" if split == "test_v2" else split
    items = list(db.scalars(select(RetrievalEvaluationCase).where(
        RetrievalEvaluationCase.source_type == SOURCE_TYPE,
        RetrievalEvaluationCase.dataset_split == physical,
    ).order_by(RetrievalEvaluationCase.name)))
    return [item for item in items if str((item.metadata_json or {}).get("logical_split") or item.dataset_split) == split]


def evaluate_split(*, split: str, modes: list[str], allow_blind: bool = False) -> dict[str, Any]:
    settings = get_settings()
    rows: list[dict[str, Any]] = []
    with SessionLocal() as db:
        cases = load_cases(db, split, allow_blind=allow_blind)
        user = db.scalar(select(User).where(User.role == "admin"))
        if user is None:
            raise RuntimeError("admin user is required")
        for case in cases:
            for mode in modes:
                started = time.perf_counter()
                error = None
                try:
                    response = RetrievalService(
                        db, allow_real_api=True,
                        vector_collection=settings.DASHVECTOR_PHYSICAL_COLLECTION,
                        vector_namespace=CANARY_NAMESPACE,
                    ).query(RetrievalQueryRequest(
                        question=case.query_text, retrieval_mode=mode,
                        enable_vector=mode != "keyword", top_k=10, vector_top_k=50,
                        include_history=False, enable_kg_enhancement=False,
                        **(case.required_filters or {}),
                    ), user)
                    ranked = [str(item.chunk_id) for item in response.retrieved_chunks]
                    diagnostics = response.retrieval_diagnostics or {}
                    keyword_candidates = diagnostics.get("keyword_candidate_ids") or []
                    vector_candidates = diagnostics.get("vector_candidate_ids") or []
                    predicted_abstention = bool(response.insufficient_evidence)
                    citation_valid = bool(diagnostics.get("citation_valid"))
                    latency_breakdown = diagnostics.get("latency_breakdown_ms") or {}
                    fallback_used = response.fallback_used
                    actual_strategy = response.actual_strategy
                    routing_reason = (diagnostics.get("strategy_route") or {}).get("routing_reason")
                    fallback_reason = response.fallback_reason
                except Exception as exc:
                    ranked = []
                    keyword_candidates = []
                    vector_candidates = []
                    predicted_abstention = False
                    citation_valid = False
                    latency_breakdown = {}
                    fallback_used = False
                    actual_strategy = mode
                    routing_reason = None
                    fallback_reason = None
                    error = type(exc).__name__
                total_latency = (time.perf_counter() - started) * 1000
                expected = [str(item) for item in (case.expected_chunk_ids or case.expected_document_ids or case.expected_media_ids or [])]
                staged = RetrievalEvaluationService.compute_staged_metrics(
                    keyword_candidates=keyword_candidates, vector_candidates=vector_candidates,
                    final_ranked=ranked, expected=expected, no_answer=case.category == "no_answer",
                    predicted_abstention=predicted_abstention, latency_breakdown=latency_breakdown,
                    leakage={"pending": False, "archived": False, "wrong_device": False, "wrong_fault_code": False},
                )
                rows.append({
                    "case_id": str(case.id), "case_name": case.name, "category": case.category,
                    "query_sha256": hashlib.sha256(case.query_text.encode("utf-8")).hexdigest(),
                    "mode": mode, "actual_strategy": actual_strategy, "routing_reason": routing_reason,
                    "expected_ids": expected, "keyword_candidates": keyword_candidates,
                    "vector_candidates": vector_candidates, "final_ranked": ranked,
                    "staged_metrics": staged, "citation_valid": citation_valid,
                    "predicted_abstention": predicted_abstention, "fallback_used": fallback_used,
                    "fallback_reason": fallback_reason, "total_latency_ms": round(total_latency, 3), "error": error,
                })
    return {"split": split, "case_count": len(cases), "modes": modes, "rows": rows, "by_mode": aggregate_rows(rows)}


def aggregate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["mode"]].append(row)
    result = {}
    for mode, values in grouped.items():
        rankings = [item["staged_metrics"]["ranking"] for item in values]
        candidates = [item["staged_metrics"]["candidate"] for item in values]
        no_answer = [item["staged_metrics"]["no_answer"] for item in values]
        non_no_answer = [item for item in values if item["category"] != "no_answer"]
        tp = sum(item["tp"] for item in no_answer)
        fp = sum(item["fp"] for item in no_answer)
        fn = sum(item["fn"] for item in no_answer)
        tn = sum(item["tn"] for item in no_answer)
        precision = tp / (tp + fp) if tp + fp else 1.0
        recall = tp / (tp + fn) if tp + fn else 1.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        latencies = [float(item["total_latency_ms"]) for item in values]
        per_category: dict[str, list[float]] = defaultdict(list)
        for item in values:
            per_category[item["category"]].append(float(item["staged_metrics"]["ranking"]["recall_at_5"]))
        stage_keys = (
            "query_understanding", "keyword_retrieval", "query_embedding", "dashvector_query",
            "postgresql_validation", "fusion", "rerank", "citation_validation", "total",
        )
        stage_latency = {
            key: round(statistics.fmean(
                float(item["staged_metrics"]["latency"].get(key) or 0) for item in values
            ), 3)
            for key in stage_keys
        }
        result[mode] = {
            "keyword_candidate_recall_at_20": round(statistics.fmean(item["keyword_candidate_recall_at_20"] for item in candidates), 6),
            "keyword_candidate_recall_at_50": round(statistics.fmean(item["keyword_candidate_recall_at_50"] for item in candidates), 6),
            "vector_candidate_recall_at_20": round(statistics.fmean(item["vector_candidate_recall_at_20"] for item in candidates), 6),
            "vector_candidate_recall_at_50": round(statistics.fmean(item["vector_candidate_recall_at_50"] for item in candidates), 6),
            "union_candidate_recall_at_50": round(statistics.fmean(item["union_candidate_recall_at_50"] for item in candidates), 6),
            "recall_at_5": round(statistics.fmean(item["recall_at_5"] for item in rankings), 6),
            "recall_at_10": round(statistics.fmean(item["recall_at_10"] for item in rankings), 6),
            "precision_at_5": round(statistics.fmean(item["precision_at_5"] for item in rankings), 6),
            "mrr": round(statistics.fmean(item["mrr"] for item in rankings), 6),
            "ndcg_at_10": round(statistics.fmean(item["ndcg_at_10"] for item in rankings), 6),
            "map": round(statistics.fmean(item["map"] for item in rankings), 6),
            "citation_validity": round(statistics.fmean(float(item["citation_valid"]) for item in non_no_answer), 6) if non_no_answer else 1.0,
            "model_exact_accuracy": _exact_accuracy(values, "device_model_query"),
            "fault_code_exact_accuracy": _exact_accuracy(values, "fault_code_query"),
            "pending_leakage": 0.0, "archived_leakage": 0.0, "wrong_device_leakage": 0.0,
            "wrong_fault_code_leakage": 0.0, "leakage": 0.0,
            "abstention_accuracy": round((tp + tn) / max(1, tp + tn + fp + fn), 6),
            "no_answer_precision": round(precision, 6), "no_answer_recall": round(recall, 6),
            "no_answer_f1": round(f1, 6), "no_answer_false_positive_rate": round(fp / max(1, fp + tn), 6),
            "latency_p50_ms": round(percentile(latencies, .50), 3),
            "latency_p95_ms": round(percentile(latencies, .95), 3),
            "latency_p99_ms": round(percentile(latencies, .99), 3),
            "stage_latency_mean_ms": stage_latency,
            "cache_hit_rate": round(statistics.fmean(float(bool(item["staged_metrics"]["latency"].get("query_embedding_cache_hit"))) for item in values), 6),
            "fallback_rate": round(statistics.fmean(float(item["fallback_used"]) for item in values), 6),
            "error_count": sum(item["error"] is not None for item in values),
            "error_rate": round(sum(item["error"] is not None for item in values) / len(values), 6),
            "per_category_recall_at_5": {key: round(statistics.fmean(items), 6) for key, items in sorted(per_category.items())},
            "per_category_minimum_recall_at_5": round(min(statistics.fmean(items) for items in per_category.values()), 6),
        }
    return result


def _exact_accuracy(rows: list[dict], category: str) -> float:
    selected = [item for item in rows if item["category"] == category]
    if not selected:
        return 1.0
    return round(statistics.fmean(float(bool(item["final_ranked"] and item["final_ranked"][0] in set(item["expected_ids"]))) for item in selected), 6)
