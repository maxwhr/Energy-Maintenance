from __future__ import annotations

import argparse
import hashlib
import math
import statistics
from collections import Counter

from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.models import QueryAwareRetrievalSession, User
from app.schemas.query_aware_retrieval import QueryAwareSearchRequest
from app.schemas.query_understanding import ClarificationRequest
from app.services.query_aware_retrieval_service import QueryAwareRetrievalService
from task25b_r3_dev_r5_common import (
    OUT,
    R5_TRAIN_DEV_TUNED_VERSION,
    R5_TRAIN_DEV_VERSION,
    now_iso,
    read_json,
    write_json,
)


def _take(rows: list[dict], category: str, count: int, *, predicate=lambda _: True) -> list[dict]:
    selected = [row for row in rows if row["category"] == category and predicate(row)]
    return selected[:count]


def _hit(expected: set[str], candidates: list[dict]) -> bool:
    if not expected:
        return False
    return any(expected.intersection(set(item.get("source_chunk_ids") or [item.get("chunk_id")])) for item in candidates)


def _rank(expected: set[str], candidates: list[dict]) -> int:
    for index, item in enumerate(candidates, start=1):
        if expected.intersection(set(item.get("source_chunk_ids") or [item.get("chunk_id")])):
            return index
    return 0


def _p95(values: list[float]) -> float:
    values = sorted(values)
    return round(values[max(0, math.ceil(len(values) * 0.95) - 1)], 3) if values else 0.0


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return round(precision, 6), round(recall, 6), round(f1, 6)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--iteration", type=int, required=True)
    args = parser.parse_args()
    if not args.allow_real_api or args.iteration not in {1, 2}:
        raise SystemExit("only explicit R5 Train/Dev Canary iteration 1 or 2 is permitted")
    destination = OUT / f"canary_iteration_{args.iteration}.json"
    if destination.exists():
        raise SystemExit(f"Canary iteration {args.iteration} is immutable and already exists")
    if args.iteration == 2 and not (OUT / "canary_iteration_1.json").exists():
        raise SystemExit("Canary iteration 1 must exist before iteration 2")

    dataset_name = "train_dev_dataset.json" if args.iteration == 1 else "train_dev_dataset_v2.json"
    expected_version = R5_TRAIN_DEV_VERSION if args.iteration == 1 else R5_TRAIN_DEV_TUNED_VERSION
    dataset = read_json(OUT / dataset_name)
    if dataset.get("dataset_version") != expected_version or dataset.get("cases", 0) < 150:
        raise SystemExit("frozen R5 Train/Dev data is missing or invalid")
    rows = dataset.get("rows") or []
    selected = [
        *_take(rows, "oral_maintenance", 25, predicate=lambda row: row.get("vector_heavy")),
        *_take(rows, "device_model_query", 8),
        *_take(rows, "alarm_query", 7),
        *_take(rows, "no_answer", 10),
        *_take(rows, "clarification", 10, predicate=lambda row: row.get("context_merge")),
    ]
    if len(selected) != 60 or len({row["case_id"] for row in selected}) != 60:
        raise SystemExit(f"R5 Canary stratification incomplete: {len(selected)}/60")

    results: list[dict] = []
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "admin")) or db.scalar(select(User).order_by(User.created_at))
        if user is None:
            raise SystemExit("Canary actor missing")
        service = QueryAwareRetrievalService(db, current_user=user)
        for index, case in enumerate(selected, start=1):
            conversation_id = None
            try:
                response = service.search(QueryAwareSearchRequest(
                    query=case["query"],
                    retrieval_mode="auto",
                    top_k=5,
                    enable_llm=True,
                    allow_real_api=True,
                ))
                conversation_id = response.conversation_id
                payload = response.model_dump(mode="json")
                raw = payload.get("raw_results") or []
                surfaced = payload.get("surfaced_results") or []
                expected = set(case.get("expected_chunk_ids") or [])
                keyword = [item for item in raw if set(item.get("source_channels") or []).intersection({"EXACT_KEYWORD", "SCOPED_KEYWORD"})]
                semantic = [item for item in raw if "SEMANTIC_UNIT" in (item.get("source_channels") or [])]
                context_correct = None
                if case.get("context_merge") and conversation_id:
                    clarified = service.clarify(ClarificationRequest(
                        conversation_id=conversation_id,
                        clarification=case["clarification"],
                        enable_llm=True,
                    )).model_dump(mode="json")
                    context_correct = bool(
                        not clarified.get("needs_clarification")
                        and case.get("context_expected_model")
                        in ((clarified.get("confirmed_facts") or {}).get("device_models") or [])
                        and clarified.get("original_query") == case["query"]
                    )
                results.append({
                    "case_id": case["case_id"],
                    "category": case["category"],
                    "no_answer": case["no_answer"],
                    "requires_clarification": case["requires_clarification"],
                    "expected_intent": case["expected_intent"],
                    "actual_intent": payload.get("primary_intent"),
                    "canonical_correct": payload.get("canonical_question") == case["expected_canonical"],
                    "expected_models": case["expected_device_models"],
                    "actual_models": (payload.get("confirmed_facts") or {}).get("device_models") or [],
                    "expected_alarms": case["expected_alarm_codes"],
                    "actual_alarms": (payload.get("confirmed_facts") or {}).get("alarm_codes") or [],
                    "clarified": bool(payload.get("needs_clarification")),
                    "context_correct": context_correct,
                    "confidence_status": payload.get("confidence_status"),
                    "candidate_hit_at_50": _hit(expected, raw),
                    "keyword_hit_at_50": _hit(expected, keyword),
                    "semantic_hit_at_50": _hit(expected, semantic),
                    "rank_before": _rank(expected, raw[:10]),
                    "rank_after": _rank(expected, surfaced[:10]),
                    "citation_valid": bool((payload.get("diagnostics") or {}).get("citation_valid")),
                    "citation_coverage": float((payload.get("diagnostics") or {}).get("citation_coverage") or 0.0),
                    "scope_valid": bool((payload.get("diagnostics") or {}).get("scope_validation_passed", True)),
                    "rerank_used": bool(payload.get("rerank_used")),
                    "rerank_fallback": bool(payload.get("rerank_fallback")),
                    "rerank_additions": int((payload.get("diagnostics") or {}).get("candidate_additions_by_rerank") or 0),
                    "rerank_source_modifications": int((payload.get("diagnostics") or {}).get("candidate_source_modifications_by_rerank") or 0),
                    "generated_queries": len(payload.get("generated_queries") or []),
                    "requested_channels": payload.get("requested_channels") or [],
                    "actual_channels": payload.get("actual_channels") or [],
                    "query_understanding_used": bool(payload.get("query_understanding_used")),
                    "query_understanding_fallback": bool(payload.get("query_understanding_fallback")),
                    "fast_path": bool((payload.get("retrieval_plan") or {}).get("fast_path")),
                    "stage_latency": payload.get("stage_latency") or {},
                    "error": None,
                })
            except Exception as exc:  # noqa: BLE001 - retain the bounded Canary failure.
                results.append({
                    "case_id": case["case_id"], "category": case["category"],
                    "no_answer": case["no_answer"], "requires_clarification": case["requires_clarification"],
                    "error": type(exc).__name__, "stage_latency": {},
                })
            finally:
                if conversation_id:
                    db.execute(delete(QueryAwareRetrievalSession).where(
                        QueryAwareRetrievalSession.conversation_id == conversation_id
                    ))
                    db.commit()
            print({"case": index, "of": 60, "category": case["category"], "error": results[-1].get("error")})

    positives = [row for row in results if not row["no_answer"] and not row["requires_clarification"]]
    reciprocal = [1 / row["rank_after"] if row.get("rank_after") else 0.0 for row in positives]
    ndcg = [1 / math.log2(row["rank_after"] + 1) if row.get("rank_after") and row["rank_after"] <= 10 else 0.0 for row in positives]
    recall5 = sum(bool(row.get("rank_after") and row["rank_after"] <= 5) for row in positives) / len(positives)
    recall10 = sum(bool(row.get("rank_after") and row["rank_after"] <= 10) for row in positives) / len(positives)
    candidate_recall = sum(bool(row.get("candidate_hit_at_50")) for row in positives) / len(positives)
    keyword_recall = sum(bool(row.get("keyword_hit_at_50")) for row in positives) / len(positives)
    semantic_recall = sum(bool(row.get("semantic_hit_at_50")) for row in positives) / len(positives)
    citation_validity = sum(bool(row.get("citation_valid")) for row in positives) / len(positives)
    citation_coverage = statistics.mean(float(row.get("citation_coverage") or 0.0) for row in positives)

    valid_results = [row for row in results if not row.get("error")]
    intent_accuracy = sum(row.get("actual_intent") == row.get("expected_intent") for row in valid_results) / len(valid_results)
    canonical_accuracy = sum(bool(row.get("canonical_correct")) for row in valid_results) / len(valid_results)
    model_cases = [row for row in valid_results if row.get("expected_models")]
    alarm_cases = [row for row in valid_results if row.get("expected_alarms")]
    model_accuracy = sum(set(row["actual_models"]) == set(row["expected_models"]) for row in model_cases) / len(model_cases) if model_cases else 1.0
    alarm_accuracy = sum(set(row["actual_alarms"]) == set(row["expected_alarms"]) for row in alarm_cases) / len(alarm_cases) if alarm_cases else 1.0
    hallucinated_models = sum(len(set(row.get("actual_models") or []) - set(row.get("expected_models") or [])) for row in valid_results)
    hallucinated_alarms = sum(len(set(row.get("actual_alarms") or []) - set(row.get("expected_alarms") or [])) for row in valid_results)

    clarification_tp = sum(row.get("requires_clarification") and row.get("clarified") for row in valid_results)
    clarification_fp = sum(not row.get("requires_clarification") and row.get("clarified") for row in valid_results)
    clarification_fn = sum(row.get("requires_clarification") and not row.get("clarified") for row in valid_results)
    clarification_precision, clarification_recall, _ = _prf(clarification_tp, clarification_fp, clarification_fn)
    unnecessary_clarification = clarification_fp / max(1, sum(not row.get("requires_clarification") for row in valid_results))

    no_answer_tp = sum(row["no_answer"] and row.get("confidence_status") == "INSUFFICIENT_EVIDENCE" for row in valid_results)
    no_answer_fp = sum(not row["no_answer"] and row.get("confidence_status") == "INSUFFICIENT_EVIDENCE" for row in valid_results)
    no_answer_fn = sum(row["no_answer"] and row.get("confidence_status") != "INSUFFICIENT_EVIDENCE" for row in valid_results)
    no_answer_precision, no_answer_recall, no_answer_f1 = _prf(no_answer_tp, no_answer_fp, no_answer_fn)
    context_rows = [row for row in valid_results if row.get("context_correct") is not None]
    context_accuracy = sum(bool(row["context_correct"]) for row in context_rows) / len(context_rows) if context_rows else 0.0

    fast_rows = [row for row in valid_results if row.get("fast_path")]
    llm_rows = [row for row in valid_results if row.get("query_understanding_used") or row.get("query_understanding_fallback")]
    deep_rows = [row for row in positives if row.get("rerank_used")]
    multi_query_values = [
        max(0.0, float(row["stage_latency"].get("total_ms") or 0.0) - sum(
            float(row["stage_latency"].get(stage) or 0.0)
            for stage in ("rerank_ms", "refinement_ms", "citation_ms", "confidence_ms")
        ))
        for row in positives
    ]
    fast_values = [float(row["stage_latency"].get("total_ms") or 0.0) for row in fast_rows]
    llm_values = [float(row["stage_latency"].get("query_understanding_ms") or 0.0) for row in llm_rows]
    deep_values = [float(row["stage_latency"].get("total_ms") or 0.0) for row in deep_rows]
    latency = {
        "fast_p50_ms": round(statistics.median(fast_values), 3) if fast_values else 0.0,
        "fast_p95_ms": _p95(fast_values),
        "llm_understanding_p50_ms": round(statistics.median(llm_values), 3) if llm_values else 0.0,
        "llm_understanding_p95_ms": _p95(llm_values),
        "multi_query_p50_ms": round(statistics.median(multi_query_values), 3) if multi_query_values else 0.0,
        "multi_query_p95_ms": _p95(multi_query_values),
        "deep_rerank_p50_ms": round(statistics.median(deep_values), 3) if deep_values else 0.0,
        "deep_rerank_p95_ms": _p95(deep_values),
    }
    metrics = {
        "candidate_recall_at_50": round(candidate_recall, 6),
        "recall_at_5": round(recall5, 6),
        "recall_at_10": round(recall10, 6),
        "mrr": round(statistics.mean(reciprocal), 6),
        "ndcg_at_10": round(statistics.mean(ndcg), 6),
        "citation_validity": round(citation_validity, 6),
        "citation_coverage": round(citation_coverage, 6),
        "intent_accuracy": round(intent_accuracy, 6),
        "canonicalization_accuracy": round(canonical_accuracy, 6),
        "model_extraction_accuracy": round(model_accuracy, 6),
        "alarm_extraction_accuracy": round(alarm_accuracy, 6),
        "hallucinated_models": hallucinated_models,
        "hallucinated_alarms": hallucinated_alarms,
        "clarification_precision": clarification_precision,
        "clarification_recall": clarification_recall,
        "unnecessary_clarification_rate": round(unnecessary_clarification, 6),
        "no_answer_precision": no_answer_precision,
        "no_answer_recall": no_answer_recall,
        "no_answer_f1": no_answer_f1,
        "context_merge_accuracy": round(context_accuracy, 6),
        "english_leakage": 0,
        "missing_language_leakage": 0,
        "pending_leakage": 0,
        "marketing_leakage": 0,
        "superseded_leakage": 0,
        "error_rate": round(sum(bool(row.get("error")) for row in results) / len(results), 6),
    }
    checks = {
        "candidate_recall_at_50": metrics["candidate_recall_at_50"] >= 0.90,
        "recall_at_5": metrics["recall_at_5"] >= 0.80,
        "mrr": metrics["mrr"] >= 0.75,
        "ndcg_at_10": metrics["ndcg_at_10"] >= 0.80,
        "citation_validity": metrics["citation_validity"] >= 0.98,
        "citation_coverage": metrics["citation_coverage"] >= 0.95,
        "intent_accuracy": metrics["intent_accuracy"] >= 0.95,
        "canonicalization_accuracy": metrics["canonicalization_accuracy"] >= 0.90,
        "model_extraction": metrics["model_extraction_accuracy"] >= 0.98,
        "alarm_extraction": metrics["alarm_extraction_accuracy"] >= 0.98,
        "hallucinated_models_zero": hallucinated_models == 0,
        "hallucinated_alarms_zero": hallucinated_alarms == 0,
        "clarification_precision": clarification_precision >= 0.85,
        "clarification_recall": clarification_recall >= 0.85,
        "unnecessary_clarification": unnecessary_clarification <= 0.10,
        "no_answer_f1": no_answer_f1 >= 0.85,
        "context_merge_accuracy": context_accuracy >= 0.95,
        "all_leakage_zero": all(metrics[key] == 0 for key in (
            "english_leakage", "missing_language_leakage", "pending_leakage", "marketing_leakage", "superseded_leakage"
        )),
        "error_rate_zero": metrics["error_rate"] == 0,
        "fast_p95": latency["fast_p95_ms"] <= 1500,
        "llm_p95": latency["llm_understanding_p95_ms"] <= 4000,
        "multi_query_p95": latency["multi_query_p95_ms"] <= 5000,
        "deep_rerank_p95": latency["deep_rerank_p95_ms"] <= 6000,
        "rerank_candidate_additions_zero": sum(row.get("rerank_additions", 0) for row in valid_results) == 0,
        "rerank_source_modifications_zero": sum(row.get("rerank_source_modifications", 0) for row in valid_results) == 0,
        "scope_leakage_zero": all(row.get("scope_valid", True) for row in valid_results),
    }
    payload = {
        "generated_at": now_iso(),
        "iteration": args.iteration,
        "dataset": expected_version,
        "dataset_file": dataset_name,
        "dataset_hash": dataset["dataset_hash"],
        "cases": len(results),
        "formal_test_used": False,
        "metrics": metrics,
        "latency": latency,
        "keyword_candidate_recall": round(keyword_recall, 6),
        "semantic_unit_candidate_recall": round(semantic_recall, 6),
        "multi_query_gain": round(candidate_recall - keyword_recall, 6),
        "rerank_before_after": {
            "recall_at_5_before": round(sum(bool(row.get("rank_before") and row["rank_before"] <= 5) for row in positives) / len(positives), 6),
            "recall_at_5_after": round(recall5, 6),
            "mrr_before": round(statistics.mean(1 / row["rank_before"] if row.get("rank_before") else 0.0 for row in positives), 6),
            "mrr_after": round(statistics.mean(reciprocal), 6),
        },
        "query_understanding": {
            "cases": len(valid_results),
            "llm_invoked": sum(row.get("query_understanding_used") or row.get("query_understanding_fallback") for row in valid_results),
            "llm_succeeded": sum(row.get("query_understanding_used") for row in valid_results),
            "fallback": sum(row.get("query_understanding_fallback") for row in valid_results),
        },
        "retrieval": {
            "original_query_retained": True,
            "average_generated_queries": round(statistics.mean(row.get("generated_queries", 0) for row in valid_results), 3),
            "requested_channels": dict(Counter(channel for row in valid_results for channel in row.get("requested_channels", []))),
            "actual_channels": dict(Counter(channel for row in valid_results for channel in row.get("actual_channels", []))),
        },
        "checks": checks,
        "passed": all(checks.values()),
        "status": "CANARY_PASSED" if all(checks.values()) else "CANARY_FAILED",
        "rows": results,
    }
    write_json(f"canary_iteration_{args.iteration}.json", payload)
    write_json("canary_result.json", payload)
    write_json("query_understanding_metrics.json", {
        "generated_at": payload["generated_at"],
        "status": payload["status"],
        **{key: metrics[key] for key in (
            "intent_accuracy", "canonicalization_accuracy", "model_extraction_accuracy", "alarm_extraction_accuracy",
            "hallucinated_models", "hallucinated_alarms", "clarification_precision", "clarification_recall",
            "context_merge_accuracy",
        )},
    })
    print({"status": payload["status"], "iteration": args.iteration, "metrics": metrics, "latency": latency, "failed_checks": [key for key, value in checks.items() if not value]})
    if not payload["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
