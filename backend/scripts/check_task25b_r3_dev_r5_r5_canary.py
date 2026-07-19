from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import QueryAwareRetrievalSession, User
from app.schemas.query_aware_retrieval import QueryAwareSearchRequest
from app.schemas.query_understanding import ClarificationRequest
from app.services.graded_relevance_metrics import dcg, direct_answer_hit, graded_mrr, requested_information_coverage_at_k
from app.services.query_aware_retrieval_service import QueryAwareRetrievalService
from task25b_r3_dev_r5_r5_common import OUT, now_iso, p95, ratio, sha256_json


DATASET = OUT / "train_dev_dataset_v1.json"
HASHES = OUT / "dataset_hash_manifest.json"
CHECKPOINT = OUT / "canary_checkpoint.json"
CASE_RESULTS = OUT / "canary_case_results.json"
CASE_RESULTS_CSV = OUT / "canary_case_results.csv"
LOCK = OUT / "canary.lock"


def _atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


@contextmanager
def _lock(iteration: int) -> Iterator[None]:
    try:
        handle = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise SystemExit("another R5-R5 Canary owns the run lock") from exc
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(json.dumps({"iteration": iteration, "pid": os.getpid(), "started_at": now_iso()}))
        yield
    finally:
        LOCK.unlink(missing_ok=True)


def _aliases(candidate: dict[str, Any]) -> set[str]:
    semantic = str(candidate.get("semantic_unit_id") or "")
    output = {
        str(candidate.get("candidate_id") or ""),
        str(candidate.get("chunk_id") or ""),
        str(candidate.get("evidence_identity") or ""),
        semantic,
        f"su:{semantic}" if semantic else "",
        *(str(value) for value in candidate.get("source_chunk_ids") or []),
    }
    output.discard("")
    return output


def _grade(case: dict[str, Any], candidate: dict[str, Any]) -> int:
    identity = case["evaluation_identity"]
    aliases = _aliases(candidate)
    grades = identity.get("relevance_grades") or {}
    grade = max((int(value) for key, value in grades.items() if key in aliases), default=0)
    # Evaluation identity contract: a direct source chunk of a labelled Unit
    # receives Unit-level credit when the mapping was frozen with the case.
    if identity.get("expected_semantic_unit_ids") and aliases.intersection(identity.get("expected_chunk_ids") or []):
        grade = max(grade, 3)
    return grade


def _canonical_correct(case: dict[str, Any], value: str) -> bool:
    terms = [str(item) for item in case.get("expected_canonical_terms") or []]
    return all(term in value for term in terms)


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return round(precision, 6), round(recall, 6), round(f1, 6)


def _evaluate(case: dict[str, Any], payload: dict[str, Any], *, context_correct: bool | None) -> dict[str, Any]:
    raw = payload.get("raw_results") or []
    surfaced = payload.get("surfaced_results") or []
    raw_grades = [_grade(case, item) for item in raw[:50]]
    surfaced_grades = [_grade(case, item) for item in surfaced[:10]]
    rank = next((index for index, grade in enumerate(surfaced_grades, start=1) if grade > 0), 0)
    identity = case["evaluation_identity"]
    ideal_grades = [3] * len(identity.get("direct_evidence_ids") or [])
    ideal_grades += [1] * len(identity.get("background_evidence_ids") or [])
    if not ideal_grades and not case.get("no_answer"):
        ideal_grades = [3]
    ideal_dcg_10 = dcg(sorted(ideal_grades, reverse=True), 10)
    ideal_dcg_5 = dcg(sorted(ideal_grades, reverse=True), 5)
    ndcg_value = dcg(surfaced_grades, 10) / ideal_dcg_10 if ideal_dcg_10 else 0.0
    ndcg_5_value = dcg(surfaced_grades, 5) / ideal_dcg_5 if ideal_dcg_5 else 0.0
    expected_requested = set(case.get("expected_requested_information") or [])
    support = [set(item.get("requested_information_support") or []) for item in surfaced]
    actual_models = (payload.get("confirmed_facts") or {}).get("device_models") or []
    actual_alarms = (payload.get("confirmed_facts") or {}).get("alarm_codes") or []
    expected_models = case.get("expected_device_models") or []
    expected_alarms = case.get("expected_alarm_codes") or []
    diagnostics = payload.get("diagnostics") or {}
    return {
        "case_id": case["case_id"],
        "category": case.get("category"),
        "no_answer": bool(case.get("no_answer")),
        "requires_clarification": bool(case.get("requires_clarification")),
        "expected_primary_intent": case.get("expected_primary_intent"),
        "actual_primary_intent": payload.get("primary_intent"),
        "expected_requested_information": sorted(expected_requested),
        "actual_requested_information": sorted(payload.get("requested_information") or []),
        "canonical_query": payload.get("canonical_question"),
        "canonical_correct": _canonical_correct(case, str(payload.get("canonical_question") or "")),
        "expected_models": expected_models,
        "actual_models": actual_models,
        "expected_alarms": expected_alarms,
        "actual_alarms": actual_alarms,
        "hallucinated_models": sorted(set(actual_models) - set(expected_models)),
        "hallucinated_alarms": sorted(set(actual_alarms) - set(expected_alarms)),
        "clarified": bool(payload.get("needs_clarification")),
        "context_correct": context_correct,
        "confidence_status": payload.get("confidence_status"),
        "candidate_hit_at_50": any(grade > 0 for grade in raw_grades),
        "rank_at_10": rank,
        "grades_at_10": surfaced_grades,
        "ndcg_at_10": round(ndcg_value, 6),
        "ndcg_at_5": round(ndcg_5_value, 6),
        "graded_mrr": round(graded_mrr(surfaced_grades), 6),
        "direct_answer_hit_at_1": direct_answer_hit(surfaced_grades, 1),
        "direct_answer_hit_at_3": direct_answer_hit(surfaced_grades, 3),
        "requested_information_coverage_at_3": round(
            requested_information_coverage_at_k(support, expected_requested, 3), 6
        ),
        "citation_valid": float(payload.get("citation_validity_ratio") or 0.0) >= 0.98,
        "citation_validity_ratio": float(payload.get("citation_validity_ratio") or 0.0),
        "citation_coverage": float(payload.get("citation_coverage_ratio") or 0.0),
        "scope_valid": bool(diagnostics.get("scope_validation_passed", True)),
        "requested_channels": payload.get("requested_channels") or [],
        "actual_channels": payload.get("actual_channels") or [],
        "generated_queries": payload.get("generated_queries") or [],
        "retrieval_plan": payload.get("retrieval_plan") or {},
        "raw_candidates": raw[:50],
        "rrf_ranking": [item.get("candidate_id") for item in raw[:50]],
        "rerank_ranking": [item.get("candidate_id") for item in surfaced[:10]],
        "surfaced_results": surfaced[:10],
        "citation_validation": {
            "valid": payload.get("citation_validity_ratio"),
            "coverage": payload.get("citation_coverage_ratio"),
        },
        "confidence": {"status": payload.get("confidence_status"), "score": payload.get("retrieval_confidence")},
        "query_understanding_mode": payload.get("query_understanding_mode"),
        "stage_latency": payload.get("stage_latency") or {},
        "collapse_groups": payload.get("collapse_groups") or [],
        "relevant_evidence_loss": int(diagnostics.get("relevant_candidates_lost_without_reason") or 0),
        "minimax_called": bool((payload.get("minimax_tiebreak") or {}).get("called")),
        "error": None,
    }


def _metrics(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, float], dict[str, bool]]:
    valid = [row for row in rows if not row.get("error")]
    positives = [row for row in valid if not row["no_answer"] and not row["requires_clarification"]]
    ranks = [int(row.get("rank_at_10") or 0) for row in positives]
    clarification_tp = sum(row["requires_clarification"] and row.get("clarified") for row in valid)
    clarification_fp = sum(not row["requires_clarification"] and row.get("clarified") for row in valid)
    clarification_fn = sum(row["requires_clarification"] and not row.get("clarified") for row in valid)
    clarification_precision, clarification_recall, _ = _prf(clarification_tp, clarification_fp, clarification_fn)
    no_answer_tp = sum(row["no_answer"] and row.get("confidence_status") == "INSUFFICIENT_EVIDENCE" for row in valid)
    no_answer_fp = sum(not row["no_answer"] and row.get("confidence_status") == "INSUFFICIENT_EVIDENCE" for row in valid)
    no_answer_fn = sum(row["no_answer"] and row.get("confidence_status") != "INSUFFICIENT_EVIDENCE" for row in valid)
    no_answer_precision, no_answer_recall, no_answer_f1 = _prf(no_answer_tp, no_answer_fp, no_answer_fn)
    requested_tp = requested_fp = requested_fn = 0
    for row in valid:
        expected = set(row.get("expected_requested_information") or [])
        actual = set(row.get("actual_requested_information") or [])
        requested_tp += len(expected & actual)
        requested_fp += len(actual - expected)
        requested_fn += len(expected - actual)
    requested_precision, requested_recall, requested_f1 = _prf(requested_tp, requested_fp, requested_fn)
    contexts = [row for row in valid if row.get("context_correct") is not None]
    metrics = {
        "candidate_recall_at_50": ratio(sum(row.get("candidate_hit_at_50") for row in positives), len(positives)),
        "recall_at_5": ratio(sum(0 < rank <= 5 for rank in ranks), len(ranks)),
        "recall_at_10": ratio(sum(0 < rank <= 10 for rank in ranks), len(ranks)),
        "mrr": round(statistics.mean(1 / rank if rank else 0.0 for rank in ranks), 6) if ranks else 0.0,
        "ndcg_at_5": round(statistics.mean(row.get("ndcg_at_5") or 0.0 for row in positives), 6) if positives else 0.0,
        "ndcg_at_10": round(statistics.mean(row.get("ndcg_at_10") or 0.0 for row in positives), 6) if positives else 0.0,
        "graded_mrr": round(statistics.mean(row.get("graded_mrr") or 0.0 for row in positives), 6) if positives else 0.0,
        "direct_answer_hit_at_1": ratio(sum(row.get("direct_answer_hit_at_1") for row in positives), len(positives)),
        "direct_answer_hit_at_3": ratio(sum(row.get("direct_answer_hit_at_3") for row in positives), len(positives)),
        "requested_information_coverage_at_3": round(statistics.mean(row.get("requested_information_coverage_at_3") or 0.0 for row in positives), 6) if positives else 0.0,
        "citation_validity": round(statistics.mean(row.get("citation_validity_ratio") or 0.0 for row in positives), 6) if positives else 0.0,
        "citation_coverage": round(statistics.mean(row.get("citation_coverage") or 0.0 for row in positives), 6) if positives else 0.0,
        "no_answer_precision": no_answer_precision,
        "no_answer_recall": no_answer_recall,
        "no_answer_f1": no_answer_f1,
        "primary_intent_accuracy": ratio(sum(row.get("actual_primary_intent") == row.get("expected_primary_intent") for row in valid), len(valid)),
        "requested_information_precision": requested_precision,
        "requested_information_recall": requested_recall,
        "requested_information_f1": requested_f1,
        "canonicalization_accuracy": ratio(sum(row.get("canonical_correct") for row in valid), len(valid)),
        "clarification_precision": clarification_precision,
        "clarification_recall": clarification_recall,
        "context_merge_accuracy": ratio(sum(row.get("context_correct") for row in contexts), len(contexts)),
        "hallucinated_models": sum(len(row.get("hallucinated_models") or []) for row in valid),
        "hallucinated_alarms": sum(len(row.get("hallucinated_alarms") or []) for row in valid),
        "scope_leakage": sum(not row.get("scope_valid", True) for row in valid),
        "error_rate": ratio(sum(bool(row.get("error")) for row in rows), len(rows)),
        "unexplained_relevant_evidence_loss": sum(row.get("relevant_evidence_loss") or 0 for row in valid),
    }
    fast = [float(row["stage_latency"].get("total_ms") or 0.0) for row in valid if row.get("query_understanding_mode") == "FAST_PATH"]
    understanding = [float(row["stage_latency"].get("query_understanding_ms") or 0.0) for row in valid]
    full = [float(row["stage_latency"].get("total_ms") or 0.0) for row in positives]
    multi = [
        max(float(row["stage_latency"].get("keyword_ms") or 0.0), float(row["stage_latency"].get("raw_vector_ms") or 0.0), float(row["stage_latency"].get("semantic_unit_ms") or 0.0))
        for row in positives
    ]
    latency = {
        "fast_path_p95_ms": p95(fast),
        "deterministic_understanding_p95_ms": p95(understanding),
        "multi_query_p95_ms": p95(multi),
        "full_deterministic_path_p95_ms": p95(full),
    }
    checks = {
        "candidate_recall_at_50": metrics["candidate_recall_at_50"] >= 0.95,
        "recall_at_5": metrics["recall_at_5"] >= 0.80,
        "recall_at_10": metrics["recall_at_10"] >= 0.85,
        "mrr": metrics["mrr"] >= 0.75,
        "ndcg_at_10": metrics["ndcg_at_10"] >= 0.80,
        "citation_validity": metrics["citation_validity"] >= 0.98,
        "citation_coverage": metrics["citation_coverage"] >= 0.95,
        "no_answer_f1": metrics["no_answer_f1"] >= 0.85,
        "primary_intent_accuracy": metrics["primary_intent_accuracy"] >= 0.95,
        "canonicalization": metrics["canonicalization_accuracy"] >= 0.90,
        "clarification_precision": metrics["clarification_precision"] >= 0.85,
        "clarification_recall": metrics["clarification_recall"] >= 0.85,
        "context_merge": metrics["context_merge_accuracy"] >= 0.95,
        "hallucinated_model_zero": metrics["hallucinated_models"] == 0,
        "hallucinated_alarm_zero": metrics["hallucinated_alarms"] == 0,
        "scope_leakage_zero": metrics["scope_leakage"] == 0,
        "error_rate_zero": metrics["error_rate"] == 0,
        "requested_information_f1": metrics["requested_information_f1"] >= 0.90,
        "direct_answer_hit_at_1": metrics["direct_answer_hit_at_1"] >= 0.70,
        "direct_answer_hit_at_3": metrics["direct_answer_hit_at_3"] >= 0.85,
        "requested_information_coverage_at_3": metrics["requested_information_coverage_at_3"] >= 0.90,
        "unexplained_relevant_evidence_loss_zero": metrics["unexplained_relevant_evidence_loss"] == 0,
        "fast_path_p95": latency["fast_path_p95_ms"] <= 1500,
        "deterministic_understanding_p95": latency["deterministic_understanding_p95_ms"] <= 100,
        "multi_query_p95": latency["multi_query_p95_ms"] <= 5000,
        "full_deterministic_path_p95": latency["full_deterministic_path_p95_ms"] <= 6000,
    }
    return metrics, latency, checks


def _materialize_case_results(checkpoint: dict[str, Any]) -> None:
    rows = sorted(checkpoint.get("rows") or [], key=lambda row: (row["iteration"], row["case_id"]))
    _atomic_json(CASE_RESULTS, {"generated_at": now_iso(), "result_count": len(rows), "rows": rows})
    fields = [
        "iteration", "case_id", "category", "expected_primary_intent", "actual_primary_intent",
        "candidate_hit_at_50", "rank_at_10", "ndcg_at_10", "direct_answer_hit_at_1",
        "direct_answer_hit_at_3", "requested_information_coverage_at_3", "confidence_status", "error",
    ]
    temporary = CASE_RESULTS_CSV.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fields})
    os.replace(temporary, CASE_RESULTS_CSV)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iteration", type=int, required=True, choices=(1, 2))
    args = parser.parse_args()
    artifact_path = OUT / f"canary_iteration_{args.iteration}.json"
    if artifact_path.exists():
        raise SystemExit(f"Canary iteration {args.iteration} is already frozen")
    if args.iteration == 2 and not (OUT / "canary_iteration_1.json").exists():
        raise SystemExit("iteration 1 must be frozen first")
    if os.getenv("TASK25B_ALLOW_FULL_REINDEX", "false").lower() != "false":
        raise SystemExit("TASK25B_ALLOW_FULL_REINDEX must remain false")
    settings = get_settings()
    if not settings.TASK25B_ALLOW_REAL_API:
        raise SystemExit("TASK25B_ALLOW_REAL_API=true is required for read-only Canary retrieval")
    settings.RAG_MINIMAX_AMBIGUITY_RESOLVER_ENABLED = False
    settings.RAG_OPTIONAL_LLM_TIEBREAK_ENABLED = False
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    hashes = json.loads(HASHES.read_text(encoding="utf-8"))
    if dataset["case_count"] != 80 or dataset["dataset_hash"] != hashes["canonical_rows_sha256"]:
        raise SystemExit("fixed dataset contract mismatch")
    checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8")) if CHECKPOINT.exists() else {
        "dataset_version": dataset["dataset_version"], "dataset_hash": dataset["dataset_hash"],
        "label_hash": dataset["label_hash"], "case_count": 80, "rows": [],
    }
    completed = {(row["iteration"], row["case_id"]) for row in checkpoint.get("rows") or []}
    iteration_rows: list[dict[str, Any]] = []
    with _lock(args.iteration), SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "admin")) or db.scalar(select(User).order_by(User.created_at))
        if user is None:
            raise SystemExit("no user available for Canary")
        service = QueryAwareRetrievalService(db, current_user=user)
        for index, case in enumerate(dataset["rows"], start=1):
            key = (args.iteration, case["case_id"])
            if key in completed:
                iteration_rows.append(next(row for row in checkpoint["rows"] if (row["iteration"], row["case_id"]) == key))
                continue
            conversation_id = None
            try:
                response = service.search(QueryAwareSearchRequest(
                    query=case["query"], retrieval_mode="auto", top_k=10,
                    enable_llm=False, allow_real_api=True,
                ))
                conversation_id = response.conversation_id
                payload = response.model_dump(mode="json")
                context_correct = None
                if case.get("context_merge") and conversation_id and payload.get("needs_clarification") and case.get("clarification"):
                    clarified = service.clarify(ClarificationRequest(
                        conversation_id=conversation_id, clarification=case["clarification"], enable_llm=False,
                    )).model_dump(mode="json")
                    context_correct = bool(
                        not clarified.get("needs_clarification")
                        and clarified.get("original_query") == case["query"]
                    )
                row = _evaluate(case, payload, context_correct=context_correct)
            except Exception as exc:  # noqa: BLE001 - frozen Canary records bounded error type.
                row = {
                    "case_id": case["case_id"], "category": case.get("category"),
                    "no_answer": bool(case.get("no_answer")),
                    "requires_clarification": bool(case.get("requires_clarification")),
                    "error": type(exc).__name__, "stage_latency": {},
                }
            finally:
                if conversation_id:
                    db.execute(delete(QueryAwareRetrievalSession).where(
                        QueryAwareRetrievalSession.conversation_id == conversation_id
                    ))
                    db.commit()
            row["iteration"] = args.iteration
            checkpoint.setdefault("rows", []).append(row)
            checkpoint["updated_at"] = now_iso()
            _atomic_json(CHECKPOINT, checkpoint)
            _materialize_case_results(checkpoint)
            iteration_rows.append(row)
            print(json.dumps({"iteration": args.iteration, "case": index, "of": 80, "error": row.get("error")}), flush=True)
    metrics, latency, checks = _metrics(iteration_rows)
    payload = {
        "generated_at": now_iso(),
        "iteration": args.iteration,
        "dataset_version": dataset["dataset_version"],
        "dataset_hash": dataset["dataset_hash"],
        "label_hash": dataset["label_hash"],
        "case_count": 80,
        "coverage_manifest": dataset["coverage_manifest"],
        "deterministic_only": True,
        "minimax_enabled": False,
        "metrics": metrics,
        "latency": latency,
        "checks": checks,
        "passed": all(checks.values()),
        "status": "QUERY_AWARE_GROUNDED_RAG_R5_PASS" if all(checks.values()) else "QUERY_AWARE_GROUNDED_RAG_R5_QUALITY_GATE_FAILED",
        "vector_mutations": {"re_embedded": 0, "re_upserted": 0},
        "rows": iteration_rows,
    }
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _atomic_json(OUT / "canary_result.json", payload)
    print(json.dumps({key: value for key, value in payload.items() if key != "rows"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
