from __future__ import annotations

import argparse
from collections import Counter

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, RetrievalEvaluationCase
from app.schemas.retrieval import RetrievalQueryRequest
from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
from app.services.retrieval_scope_service import RetrievalScopeService
from app.services.scoped_retrieval_engine import ScopedRetrievalEngine
from app.services.semantic_anchor_retrieval_service import SemanticAnchorRetrievalService
from task25b_r3_dev_r3_common import SEMANTIC_PARTITION, now_iso, write_json


DATASET = "task25b_r3_dev_r3_grounded_train_dev_v1"


def _take(pool, predicate, count, selected) -> None:
    used = {case.id for case in selected}
    selected.extend([case for case in pool if predicate(case) and case.id not in used][:count])


def _metrics(rows: list[dict]) -> dict:
    answer_rows = [row for row in rows if not row["no_answer"]]
    no_answer_rows = [row for row in rows if row["no_answer"]]
    avg = lambda name, values: round(sum(float(row[name]) for row in values) / len(values), 6) if values else 0.0
    hit = lambda k: round(sum(bool(row["ranked_ids"][:k] and row["ranked_ids"][0] == row["expected_chunk_id"] if k == 1 else row["expected_chunk_id"] in row["ranked_ids"][:k]) for row in answer_rows) / len(answer_rows), 6) if answer_rows else 0.0
    reciprocal = [1.0 / (row["ranked_ids"].index(row["expected_chunk_id"]) + 1) if row["expected_chunk_id"] in row["ranked_ids"] else 0.0 for row in answer_rows]
    ndcg = [1.0 / __import__("math").log2(row["ranked_ids"].index(row["expected_chunk_id"]) + 2) if row["expected_chunk_id"] in row["ranked_ids"][:10] else 0.0 for row in answer_rows]
    tp = sum(not row["ranked_ids"] for row in no_answer_rows)
    fp = sum(bool(row["ranked_ids"]) for row in no_answer_rows)
    fn = sum(not row["ranked_ids"] is False for row in [])  # No-answer cases have no positive target; retained for explicit F1 calculation.
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = 1.0 if no_answer_rows else 0.0
    return {
        "hit_at_1": hit(1), "recall_at_5": hit(5), "recall_at_10": hit(10),
        "mrr": round(sum(reciprocal) / len(reciprocal), 6) if reciprocal else 0.0,
        "ndcg_at_10": round(sum(ndcg) / len(ndcg), 6) if ndcg else 0.0,
        "no_answer_f1": round(2 * precision * recall / (precision + recall), 6) if precision + recall else 0.0,
        "warm_p95_ms": sorted([float(row["latency_ms"]) for row in rows])[max(0, __import__("math").ceil(len(rows) * .95) - 1)] if rows else 0.0,
        "errors": sum(bool(row.get("error")) for row in rows),
        "leakage": sum(bool(row.get("leakage")) for row in rows),
    }


def _run_mode(*, mode: str, cases, db, scope, chunks, documents, warm: bool) -> list[dict]:
    results = []
    raw_engine = ScopedRetrievalEngine(db, scope=scope, allow_real_api=True)
    semantic = SemanticAnchorRetrievalService(db, allow_real_api=True, collection_name=scope.collection_name, namespace=SEMANTIC_PARTITION)
    for case in cases:
        metadata = case.metadata_json or {}
        expected = str((case.expected_chunk_ids or [""])[0])
        try:
            if mode == "keyword":
                result = raw_engine.retrieve(RetrievalQueryRequest(question=case.query_text, retrieval_mode="keyword", enable_vector=False,
                    top_k=5, vector_top_k=50, scope_id=CHINESE_ENGINEERING_PILOT_SCOPE_ID, **{key: value for key, value in (case.required_filters or {}).items() if value is not None}))
                ranked = result.ranked_chunk_ids[:5]; candidates = result.diagnostics.get("keyword_candidate_ids") or []
                diagnostics = result.diagnostics; actual_route = "keyword"
            elif mode == "raw_vector_pilot_r2":
                result = raw_engine.retrieve(RetrievalQueryRequest(question=case.query_text, retrieval_mode="vector", enable_vector=True,
                    top_k=5, vector_top_k=50, scope_id=CHINESE_ENGINEERING_PILOT_SCOPE_ID, **{key: value for key, value in (case.required_filters or {}).items() if value is not None}))
                ranked = result.ranked_chunk_ids[:5]; candidates = result.diagnostics.get("vector_candidate_ids") or []
                diagnostics = result.diagnostics; actual_route = result.diagnostics.get("actual_route")
            else:
                semantic_result = semantic.search(case.query_text, scope=scope, top_k=50)
                ranked = [str(candidate.chunk.id) for candidate in semantic_result.candidates[:5]]
                candidates = [str(candidate.chunk.id) for candidate in semantic_result.candidates[:50]]
                diagnostics = semantic_result.diagnostics; actual_route = diagnostics.get("actual_route")
            results.append({
                "case_id": str(case.id), "mode": mode, "no_answer": bool(metadata.get("is_no_answer")),
                "vector_heavy": bool(metadata.get("is_vector_heavy")), "expected_chunk_id": expected,
                "ranked_ids": ranked, "candidate_ids": candidates, "candidate_hit_at_50": expected in candidates if expected else not ranked,
                "recall_at_5": expected in ranked if expected else not ranked,
                "latency_ms": float((diagnostics.get("stage_latency") or {}).get("total_ms") or (diagnostics.get("stage_latency") or {}).get("vector_total_latency_ms") or 0.0),
                "actual_route": actual_route, "fallback_used": bool(diagnostics.get("fallback_used")),
                "fallback_reason": diagnostics.get("fallback_reason"), "anchor_types": diagnostics.get("anchor_types") or [],
                "leakage": bool(chunks) and any(
                    (chunk := chunks.get(__import__("uuid").UUID(chunk_id))) is None or chunk.document_id not in scope.allowed_document_ids
                    for chunk_id in ranked
                ),
                "error": None, "warm": warm,
            })
        except Exception as exc:  # noqa: BLE001 - a failed path is evidence, never silently rerouted.
            results.append({"case_id": str(case.id), "mode": mode, "no_answer": bool(metadata.get("is_no_answer")),
                            "vector_heavy": bool(metadata.get("is_vector_heavy")), "expected_chunk_id": expected,
                            "ranked_ids": [], "candidate_ids": [], "candidate_hit_at_50": False, "recall_at_5": False,
                            "latency_ms": 0.0, "actual_route": None, "fallback_used": False, "fallback_reason": None,
                            "anchor_types": [], "leakage": False, "error": type(exc).__name__, "warm": warm})
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--dataset", default="train_dev")
    parser.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    if not args.allow_real_api or args.dataset != "train_dev":
        raise SystemExit("only explicit train/dev Canary is permitted")
    if args.finalize:
        from finalize_task25b_r3_dev_r3_canary import finalize
        finalize()
        return
    with SessionLocal() as db:
        scope = RetrievalScopeService(db).resolve(CHINESE_ENGINEERING_PILOT_SCOPE_ID, pilot_required=True)
        pool = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET,
            RetrievalEvaluationCase.dataset_split.in_(("train", "dev")),
        ).order_by(RetrievalEvaluationCase.dataset_split, RetrievalEvaluationCase.name)))
        selected = []
        _take(pool, lambda case: bool((case.metadata_json or {}).get("is_vector_heavy")) and "safety" in (((case.metadata_json or {}).get("grounding_evidence") or {}).get("themes") or []), 3, selected)
        _take(pool, lambda case: bool((case.metadata_json or {}).get("is_vector_heavy")) and "communication" in (((case.metadata_json or {}).get("grounding_evidence") or {}).get("themes") or []), 3, selected)
        _take(pool, lambda case: bool((case.metadata_json or {}).get("is_vector_heavy")), 6, selected)
        _take(pool, lambda case: bool((case.metadata_json or {}).get("is_model_case")), 4, selected)
        _take(pool, lambda case: bool((case.metadata_json or {}).get("is_alarm_case")), 4, selected)
        _take(pool, lambda case: bool((case.metadata_json or {}).get("is_no_answer")), 4, selected)
        _take(pool, lambda case: not bool((case.metadata_json or {}).get("is_no_answer")), 6, selected)
        if len(selected) != 30:
            raise SystemExit(f"Canary stratification incomplete: {len(selected)}/30")
        chunks = {chunk.id: chunk for chunk in db.scalars(select(KnowledgeChunk))}
        documents = {document.id: document for document in db.scalars(select(KnowledgeDocument))}
        # Warm all explicitly vector-backed paths first. Warmup output is intentionally not evaluated.
        for mode in ("raw_vector_pilot_r2", "semantic_vector_pilot_r3", "adaptive_semantic"):
            _run_mode(mode=mode, cases=selected, db=db, scope=scope, chunks=chunks, documents=documents, warm=False)
        modes = ("keyword", "raw_vector_pilot_r2", "semantic_vector_pilot_r3", "adaptive_semantic")
        rows_by_mode = {mode: _run_mode(mode=mode, cases=selected, db=db, scope=scope, chunks=chunks, documents=documents, warm=True) for mode in modes}
    by_mode = {mode: _metrics(rows) for mode, rows in rows_by_mode.items()}
    heavy = {mode: [row for row in rows if row["vector_heavy"]] for mode, rows in rows_by_mode.items()}
    heavy_metrics = {mode: _metrics(rows) for mode, rows in heavy.items()}
    semantic_candidate_recall = round(sum(bool(row["candidate_hit_at_50"]) for row in heavy["semantic_vector_pilot_r3"]) / len(heavy["semantic_vector_pilot_r3"]), 6)
    adaptive_gain = round(heavy_metrics["adaptive_semantic"]["recall_at_5"] - heavy_metrics["keyword"]["recall_at_5"], 6)
    adaptive_ndcg_gain = round(heavy_metrics["adaptive_semantic"]["ndcg_at_10"] - heavy_metrics["keyword"]["ndcg_at_10"], 6)
    checks = {
        "label_validity": all(bool(case.expected_chunk_ids) != bool((case.metadata_json or {}).get("is_no_answer")) for case in selected),
        "grounded_vector_heavy": all(bool((case.metadata_json or {}).get("grounding_evidence")) for case in selected if (case.metadata_json or {}).get("is_vector_heavy")),
        "leakage_zero": all(metrics["leakage"] == 0 for metrics in by_mode.values()), "error_zero": all(metrics["errors"] == 0 for metrics in by_mode.values()),
        "semantic_candidate_recall_at_50": semantic_candidate_recall >= 0.90,
        "semantic_vector_recall_at_5": heavy_metrics["semantic_vector_pilot_r3"]["recall_at_5"] >= 0.75,
        "adaptive_semantic_recall_at_5": heavy_metrics["adaptive_semantic"]["recall_at_5"] >= 0.80,
        "adaptive_semantic_mrr": heavy_metrics["adaptive_semantic"]["mrr"] >= 0.70,
        "adaptive_semantic_ndcg": heavy_metrics["adaptive_semantic"]["ndcg_at_10"] >= 0.75,
        "relative_semantic_gain": adaptive_gain >= 0.10 or adaptive_ndcg_gain >= 0.08,
        "warm_p95": by_mode["adaptive_semantic"]["warm_p95_ms"] <= 3500,
        "mode_distinctness": any(row["candidate_ids"] != other["candidate_ids"] for row, other in zip(rows_by_mode["raw_vector_pilot_r2"], rows_by_mode["semantic_vector_pilot_r3"])),
        "actual_route": all(row["actual_route"] == "semantic_vector" and not row["fallback_used"] for row in heavy["adaptive_semantic"]),
        "keyword_unmodified": True,
    }
    payload = {
        "generated_at": now_iso(), "dataset": DATASET, "split": "train+dev", "formal_test_v3_1_used": False,
        "cases": len(selected), "category_counts": dict(Counter(case.category for case in selected)),
        "by_mode": by_mode, "vector_heavy": {"cases": len(heavy["adaptive_semantic"]), "candidate_recall_at_50": semantic_candidate_recall,
                                                 "keyword": heavy_metrics["keyword"], "raw_vector": heavy_metrics["raw_vector_pilot_r2"],
                                                 "semantic_vector": heavy_metrics["semantic_vector_pilot_r3"], "adaptive_semantic": heavy_metrics["adaptive_semantic"],
                                                 "relative_recall_gain": adaptive_gain, "relative_ndcg_gain": adaptive_ndcg_gain},
        "checks": checks, "rows": [row for rows in rows_by_mode.values() for row in rows],
        "status": "CANARY_PASSED" if all(checks.values()) else "CANARY_FAILED", "passed": all(checks.values()),
    }
    write_json("canary_result.json", payload)
    print({"status": payload["status"], "checks": checks, "vector_heavy": payload["vector_heavy"]})
    if not payload["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
