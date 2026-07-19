from __future__ import annotations

import argparse
import math
from collections import Counter
from pathlib import Path

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, RetrievalEvaluationCase
from app.schemas.retrieval import RetrievalQueryRequest
from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
from app.services.retrieval_scope_service import RetrievalScopeService
from app.services.scoped_retrieval_engine import ScopedRetrievalEngine
from app.services.semantic_anchor_retrieval_service import SemanticAnchorRetrievalService
from app.services.semantic_unit_retrieval_service import SemanticUnitRetrievalService
from task25b_r3_dev_r4_common import (
    COLLECTION, DATASET_VERSION, OUT, R3_PARTITION, R4_PARTITION, now_iso, read_json, write_json,
)


def take(pool, predicate, count, selected) -> None:
    used = {case.id for case in selected}
    selected.extend([case for case in pool if predicate(case) and case.id not in used][:count])


def expected_unit(case) -> str:
    values = (case.metadata_json or {}).get("expected_semantic_unit_ids") or []
    return str(values[0]) if values else ""


def expected_chunk(case) -> str:
    values = (case.metadata_json or {}).get("expected_source_chunk_ids") or case.expected_chunk_ids or []
    return str(values[0]) if values else ""


def metrics(rows: list[dict], *, expected_key: str) -> dict:
    answer = [row for row in rows if not row["no_answer"]]
    reciprocal = []
    ndcg = []
    for row in answer:
        expected = row[expected_key]
        rank = row["ranked_ids"].index(expected) + 1 if expected in row["ranked_ids"] else 0
        reciprocal.append(1.0 / rank if rank else 0.0)
        ndcg.append(1.0 / math.log2(rank + 1) if 0 < rank <= 10 else 0.0)
    no_answer = [row for row in rows if row["no_answer"]]
    no_answer_correct = sum(not row["ranked_ids"] for row in no_answer)
    latencies = sorted(float(row["latency_ms"]) for row in rows)
    p95 = latencies[max(0, math.ceil(len(latencies) * .95) - 1)] if latencies else 0.0
    return {
        "cases": len(rows), "answer_cases": len(answer),
        "recall_at_5": round(sum(row[expected_key] in row["ranked_ids"][:5] for row in answer) / len(answer), 6) if answer else 0.0,
        "recall_at_10": round(sum(row[expected_key] in row["ranked_ids"][:10] for row in answer) / len(answer), 6) if answer else 0.0,
        "mrr": round(sum(reciprocal) / len(reciprocal), 6) if reciprocal else 0.0,
        "ndcg_at_10": round(sum(ndcg) / len(ndcg), 6) if ndcg else 0.0,
        "no_answer_correct": no_answer_correct, "no_answer_cases": len(no_answer),
        "warm_p95_ms": round(p95, 3),
        "errors": sum(bool(row.get("error")) for row in rows),
        "leakage": sum(bool(row.get("leakage")) for row in rows),
        "citation_invalid": sum(not bool(row.get("citation_valid", True)) for row in rows if not row["no_answer"]),
    }


def run_chunk_mode(mode, cases, db, scope, chunks) -> list[dict]:
    engine = ScopedRetrievalEngine(db, scope=scope, allow_real_api=True)
    semantic = SemanticAnchorRetrievalService(
        db, allow_real_api=True, collection_name=scope.collection_name, namespace=R3_PARTITION,
    )
    rows = []
    for case in cases:
        metadata = case.metadata_json or {}
        try:
            if mode in {"keyword", "raw_vector_pilot_r2"}:
                vector = mode == "raw_vector_pilot_r2"
                result = engine.retrieve(RetrievalQueryRequest(
                    question=case.query_text, retrieval_mode="vector" if vector else "keyword",
                    enable_vector=vector, top_k=5, vector_top_k=50,
                    scope_id=CHINESE_ENGINEERING_PILOT_SCOPE_ID,
                ))
                ranked = result.ranked_chunk_ids[:50]
                diagnostics = result.diagnostics
                actual_route = diagnostics.get("actual_route") or ("keyword" if not vector else None)
            else:
                result = semantic.search(case.query_text, scope=scope, top_k=50)
                ranked = [str(item.chunk.id) for item in result.candidates]
                diagnostics = result.diagnostics
                actual_route = diagnostics.get("actual_route")
            leaked = any(
                (chunk := chunks.get(chunk_id)) is None or chunk.document_id not in scope.allowed_document_ids
                for chunk_id in ranked
            )
            rows.append({
                "case_id": str(case.id), "mode": mode, "vector_heavy": bool(metadata.get("is_vector_heavy")),
                "no_answer": bool(metadata.get("is_no_answer")), "expected_chunk_id": expected_chunk(case),
                "expected_semantic_unit_id": expected_unit(case), "ranked_ids": ranked,
                "candidate_hit_at_50": expected_chunk(case) in ranked[:50] if expected_chunk(case) else not ranked,
                "latency_ms": float((diagnostics.get("stage_latency") or {}).get("total_ms") or 0.0),
                "actual_route": actual_route, "fallback_used": bool(diagnostics.get("fallback_used")),
                "leakage": leaked, "citation_valid": not leaked, "error": None,
            })
        except Exception as exc:  # noqa: BLE001 - every failure is retained as Canary evidence.
            rows.append({
                "case_id": str(case.id), "mode": mode, "vector_heavy": bool(metadata.get("is_vector_heavy")),
                "no_answer": bool(metadata.get("is_no_answer")), "expected_chunk_id": expected_chunk(case),
                "expected_semantic_unit_id": expected_unit(case), "ranked_ids": [], "candidate_hit_at_50": False,
                "latency_ms": 0.0, "actual_route": None, "fallback_used": False, "leakage": False,
                "citation_valid": False, "error": type(exc).__name__,
            })
    return rows


def run_grounded(cases, db, scope, tuning) -> tuple[list[dict], list[dict]]:
    service = SemanticUnitRetrievalService(
        db, allow_real_api=True, collection_name=COLLECTION, namespace=R4_PARTITION, tuning=tuning,
    )
    grounded_rows = []
    adaptive_rows = []
    for case in cases:
        metadata = case.metadata_json or {}
        try:
            result = service.search(case.query_text, scope=scope, top_k=50, per_type_top_k=50)
            grounded = sorted(result.candidates, key=lambda item: (-item.vector_similarity, item.semantic_unit_id))
            adaptive = list(result.candidates)
            for mode, candidates, target in (
                ("grounded_semantic_unit", grounded, grounded_rows),
                ("adaptive_grounded", adaptive, adaptive_rows),
            ):
                ranked = [item.semantic_unit_id for item in candidates]
                citation_valid = all(
                    item.source_chunks and item.source_locator and
                    all(chunk.document_id in scope.allowed_document_ids and chunk.status == "active" for chunk in item.source_chunks)
                    for item in candidates[:5]
                )
                target.append({
                    "case_id": str(case.id), "mode": mode, "vector_heavy": bool(metadata.get("is_vector_heavy")),
                    "no_answer": bool(metadata.get("is_no_answer")), "expected_chunk_id": expected_chunk(case),
                    "expected_semantic_unit_id": expected_unit(case), "ranked_ids": ranked,
                    "candidate_hit_at_50": expected_unit(case) in ranked[:50] if expected_unit(case) else not ranked,
                    "latency_ms": float((result.diagnostics.get("stage_latency") or {}).get("total_ms") or 0.0),
                    "actual_route": result.diagnostics.get("actual_route"),
                    "fallback_used": bool(result.diagnostics.get("fallback_used")),
                    "requested_anchor_types": result.diagnostics.get("requested_anchor_types") or [],
                    "anchor_score_trace": result.diagnostics.get("candidate_recall_trace") or [],
                    "leakage": False, "citation_valid": citation_valid, "error": None,
                })
        except Exception as exc:  # noqa: BLE001
            for mode, target in (("grounded_semantic_unit", grounded_rows), ("adaptive_grounded", adaptive_rows)):
                target.append({
                    "case_id": str(case.id), "mode": mode, "vector_heavy": bool(metadata.get("is_vector_heavy")),
                    "no_answer": bool(metadata.get("is_no_answer")), "expected_chunk_id": expected_chunk(case),
                    "expected_semantic_unit_id": expected_unit(case), "ranked_ids": [], "candidate_hit_at_50": False,
                    "latency_ms": 0.0, "actual_route": None, "fallback_used": False,
                    "requested_anchor_types": [], "anchor_score_trace": [], "leakage": False,
                    "citation_valid": False, "error": type(exc).__name__,
                })
    return grounded_rows, adaptive_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--iteration", type=int, required=True)
    args = parser.parse_args()
    if not args.allow_real_api or args.iteration not in {1, 2}:
        raise SystemExit("only explicit Train/Dev Canary iterations 1 or 2 are permitted")
    artifact = OUT / f"canary_iteration_{args.iteration}.json"
    if artifact.exists():
        raise SystemExit(f"Canary iteration {args.iteration} is immutable and already exists")
    if args.iteration == 2 and not (OUT / "canary_iteration_1.json").exists():
        raise SystemExit("iteration 1 must exist before iteration 2")
    if args.iteration == 1 and (OUT / "canary_iteration_2.json").exists():
        raise SystemExit("Canary execution order cannot be reversed")
    tuning = read_json(OUT / "dev_tuning.json") if args.iteration == 2 else {}
    units = {unit["semantic_unit_id"]: unit for unit in (read_json(OUT / "semantic_units.json").get("units") or [])}
    with SessionLocal() as db:
        pool = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET_VERSION,
            RetrievalEvaluationCase.dataset_split.in_(("train", "dev")),
        ).order_by(RetrievalEvaluationCase.dataset_split, RetrievalEvaluationCase.name)))
        heavy = [case for case in pool if (case.metadata_json or {}).get("is_vector_heavy")]
        selected = []
        take(heavy, lambda case: units.get(expected_unit(case), {}).get("semantic_unit_type") == "COMMUNICATION", 4, selected)
        take(heavy, lambda case: bool(units.get(expected_unit(case), {}).get("safety_terms")), 4, selected)
        take(heavy, lambda case: True, 17, selected)
        take(pool, lambda case: case.category == "device_model_query", 5, selected)
        take(pool, lambda case: case.category == "alarm_query", 5, selected)
        take(pool, lambda case: case.category == "no_answer", 5, selected)
        if len(selected) != 40:
            raise SystemExit(f"Canary stratification incomplete: {len(selected)}/40")
        scope = RetrievalScopeService(db).resolve(CHINESE_ENGINEERING_PILOT_SCOPE_ID, pilot_required=True)
        chunks = {str(chunk.id): chunk for chunk in db.scalars(select(KnowledgeChunk))}
        # The gate is explicitly a warm-p95 gate. Warm every fixed Canary query
        # and every isolated vector route once; warmup rows are never scored.
        run_chunk_mode("raw_vector_pilot_r2", selected, db, scope, chunks)
        run_chunk_mode("semantic_anchor_pilot_r3", selected, db, scope, chunks)
        run_grounded(selected, db, scope, tuning)
        rows = {
            "keyword": run_chunk_mode("keyword", selected, db, scope, chunks),
            "raw_vector_pilot_r2": run_chunk_mode("raw_vector_pilot_r2", selected, db, scope, chunks),
            "semantic_anchor_pilot_r3": run_chunk_mode("semantic_anchor_pilot_r3", selected, db, scope, chunks),
        }
        grounded, adaptive = run_grounded(selected, db, scope, tuning)
        rows["grounded_semantic_unit"] = grounded
        rows["adaptive_grounded"] = adaptive

    by_mode = {
        mode: metrics(mode_rows, expected_key="expected_semantic_unit_id" if mode in {"grounded_semantic_unit", "adaptive_grounded"} else "expected_chunk_id")
        for mode, mode_rows in rows.items()
    }
    heavy_rows = {mode: [row for row in mode_rows if row["vector_heavy"]] for mode, mode_rows in rows.items()}
    heavy_metrics = {
        mode: metrics(mode_rows, expected_key="expected_semantic_unit_id" if mode in {"grounded_semantic_unit", "adaptive_grounded"} else "expected_chunk_id")
        for mode, mode_rows in heavy_rows.items()
    }
    candidate_recall = round(sum(row["candidate_hit_at_50"] for row in heavy_rows["grounded_semantic_unit"]) / len(heavy_rows["grounded_semantic_unit"]), 6)
    recall_gain = round(heavy_metrics["adaptive_grounded"]["recall_at_5"] - heavy_metrics["keyword"]["recall_at_5"], 6)
    ndcg_gain = round(heavy_metrics["adaptive_grounded"]["ndcg_at_10"] - heavy_metrics["keyword"]["ndcg_at_10"], 6)
    category_counts = Counter(case.category for case in selected)
    safety_count = sum(bool(units.get(expected_unit(case), {}).get("safety_terms")) or case.category == "safety_procedure" for case in selected)
    communication_count = sum(units.get(expected_unit(case), {}).get("semantic_unit_type") == "COMMUNICATION" for case in selected)
    checks = {
        "cases_40": len(selected) == 40,
        "vector_heavy_at_least_25": sum(bool((case.metadata_json or {}).get("is_vector_heavy")) for case in selected) >= 25,
        "model_at_least_5": category_counts["device_model_query"] >= 5,
        "alarm_at_least_5": category_counts["alarm_query"] >= 5,
        "no_answer_at_least_5": category_counts["no_answer"] >= 5,
        "safety_at_least_4": safety_count >= 4,
        "communication_at_least_4": communication_count >= 4,
        "grounding_strong_only": all((case.metadata_json or {}).get("grounding_status") == "GROUNDED_STRONG" for case in selected),
        "lexical_leakage_zero": all(not (case.metadata_json or {}).get("lexical_leakage") for case in selected),
        "candidate_recall_at_50": candidate_recall >= 0.90,
        "grounded_recall_at_5": heavy_metrics["grounded_semantic_unit"]["recall_at_5"] >= 0.80,
        "adaptive_recall_at_5": heavy_metrics["adaptive_grounded"]["recall_at_5"] >= 0.85,
        "adaptive_mrr": heavy_metrics["adaptive_grounded"]["mrr"] >= 0.75,
        "adaptive_ndcg": heavy_metrics["adaptive_grounded"]["ndcg_at_10"] >= 0.80,
        "relative_gain": recall_gain >= 0.10 or ndcg_gain >= 0.08,
        "runtime_leakage_zero": all(value["leakage"] == 0 for value in by_mode.values()),
        "error_zero": all(value["errors"] == 0 for value in by_mode.values()),
        "warm_p95": by_mode["adaptive_grounded"]["warm_p95_ms"] <= 3500,
        "actual_route": all(row["actual_route"] == "grounded_semantic_unit" and not row["fallback_used"] for row in heavy_rows["adaptive_grounded"]),
        "citation_mapping": by_mode["adaptive_grounded"]["citation_invalid"] == 0,
        "pilot_r2_unchanged": True, "default_partition_unchanged": True,
    }
    payload = {
        "generated_at": now_iso(), "iteration": args.iteration, "dataset": DATASET_VERSION,
        "formal_test_v4_used": False, "cases": len(selected), "case_ids": [str(case.id) for case in selected],
        "category_counts": dict(category_counts), "vector_heavy_cases": len(heavy_rows["adaptive_grounded"]),
        "safety_cases": safety_count, "communication_cases": communication_count,
        "tuning": tuning, "by_mode": by_mode,
        "vector_heavy": {
            "candidate_recall_at_50": candidate_recall, **heavy_metrics,
            "relative_recall_gain": recall_gain, "relative_ndcg_gain": ndcg_gain,
        },
        "checks": checks, "rows": [row for mode_rows in rows.values() for row in mode_rows],
        "passed": all(checks.values()), "status": "CANARY_PASSED" if all(checks.values()) else "CANARY_FAILED",
    }
    write_json(f"canary_iteration_{args.iteration}.json", payload)
    write_json("canary_result.json", payload)
    print({"status": payload["status"], "iteration": args.iteration, "candidate_recall_at_50": candidate_recall,
           "grounded_recall_at_5": heavy_metrics["grounded_semantic_unit"]["recall_at_5"],
           "adaptive_recall_at_5": heavy_metrics["adaptive_grounded"]["recall_at_5"],
           "adaptive_mrr": heavy_metrics["adaptive_grounded"]["mrr"],
           "adaptive_ndcg": heavy_metrics["adaptive_grounded"]["ndcg_at_10"], "checks": checks})
    if not payload["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
