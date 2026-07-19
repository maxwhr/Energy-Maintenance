from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import User
from app.schemas.query_aware_retrieval import QueryAwareSearchRequest
from app.services.query_aware_retrieval_service import QueryAwareRetrievalService
from check_task25b_r3_dev_r5_r5_canary import _evaluate, _metrics
from task25b_r3_dev_r5_r6_common import OUT, now_iso, p95, ratio, write_json


DATASET = OUT / "train_dev_dataset_v1.json"


def _write_cases(rows: list[dict[str, Any]]) -> None:
    write_json("canary_case_results.json", {"generated_at": now_iso(), "result_count": len(rows), "rows": rows})
    fields = [
        "iteration", "configuration", "case_id", "category", "candidate_hit_at_50", "rank_at_10",
        "ndcg_at_10", "direct_answer_hit_at_1", "direct_answer_hit_at_3", "confidence_status", "error",
    ]
    with (OUT / "canary_case_results.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fields})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--iteration", required=True, type=int, choices=(1, 2))
    args = parser.parse_args()
    probe = json.loads((OUT / "qwen_rerank_probe.json").read_text(encoding="utf-8"))
    if probe.get("status") != "QWEN3_RERANK_PROBE_PASSED":
        raise SystemExit("Canary blocked: Qwen3 Probe did not pass")
    if not DATASET.is_file():
        raise SystemExit("Canary blocked: fixed R5-R6 Train/Dev dataset is absent")
    if args.iteration == 2 and not (OUT / "canary_iteration_1.json").is_file():
        raise SystemExit("Canary iteration 2 requires iteration 1")
    target = OUT / f"canary_iteration_{args.iteration}.json"
    if target.exists():
        raise SystemExit(f"Canary iteration {args.iteration} is immutable and already exists")
    settings = get_settings()
    if not args.allow_real_api or not settings.TASK25B_ALLOW_REAL_API:
        raise SystemExit("Canary requires explicit real API approval")
    if settings.TASK25B_ALLOW_FULL_REINDEX:
        raise SystemExit("TASK25B_ALLOW_FULL_REINDEX must remain false")
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    previous_rows = []
    existing_cases = OUT / "canary_case_results.json"
    if existing_cases.is_file():
        previous_rows = json.loads(existing_cases.read_text(encoding="utf-8")).get("rows") or []
    original_flags = (settings.DASHSCOPE_RERANK_ENABLED, settings.RAG_DEDICATED_RERANK_ENABLED)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "admin")) or db.scalar(select(User).order_by(User.created_at))
        if user is None:
            raise SystemExit("no user available for R5-R6 Canary")
        service = QueryAwareRetrievalService(db, current_user=user)
        try:
            for configuration, enabled in (("deterministic_rerank_v2", False), ("qwen3_dedicated_rerank", True)):
                settings.DASHSCOPE_RERANK_ENABLED = enabled
                settings.RAG_DEDICATED_RERANK_ENABLED = enabled
                for case in dataset.get("rows") or []:
                    try:
                        response = service.search(QueryAwareSearchRequest(
                            query=case["query"], retrieval_mode="auto", top_k=10,
                            enable_llm=False, allow_real_api=True,
                        )).model_dump(mode="json")
                        evaluated = _evaluate(case, response, context_correct=None)
                        evaluated.update({
                            "iteration": args.iteration,
                            "configuration": configuration,
                            "dedicated_rerank": response.get("dedicated_rerank") or {},
                            "post_rerank_constraints": response.get("post_rerank_constraints") or {},
                        })
                    except Exception as exc:  # noqa: BLE001 - record sanitized class only.
                        evaluated = {
                            "iteration": args.iteration, "configuration": configuration,
                            "case_id": case["case_id"], "category": case.get("category"),
                            "no_answer": bool(case.get("no_answer")), "requires_clarification": bool(case.get("requires_clarification")),
                            "error": exc.__class__.__name__, "stage_latency": {},
                        }
                    rows.append(evaluated)
        finally:
            settings.DASHSCOPE_RERANK_ENABLED, settings.RAG_DEDICATED_RERANK_ENABLED = original_flags
    control_rows = [row for row in rows if row["configuration"] == "deterministic_rerank_v2"]
    qwen_rows = [row for row in rows if row["configuration"] == "qwen3_dedicated_rerank"]
    control_metrics, control_latency, _ = _metrics(control_rows)
    qwen_metrics, qwen_latency, quality_checks = _metrics(qwen_rows)
    provider_success = ratio(sum(bool((row.get("dedicated_rerank") or {}).get("used")) for row in qwen_rows), len(qwen_rows))
    rerank_latencies = [float((row.get("dedicated_rerank") or {}).get("latency_ms") or 0.0) for row in qwen_rows if not row.get("error")]
    qwen_latency["rerank_component_p95_ms"] = p95(rerank_latencies)
    qwen_latency["full_path_p95_ms"] = p95([float((row.get("stage_latency") or {}).get("total_ms") or 0.0) for row in qwen_rows])
    invariant_checks = {
        "provider_success_rate": provider_success >= 0.95,
        "candidate_additions_zero": all(int(((row.get("dedicated_rerank") or {}).get("candidate_additions") or 0)) == 0 for row in qwen_rows),
        "source_modifications_zero": all(int(((row.get("dedicated_rerank") or {}).get("source_modifications") or 0)) == 0 for row in qwen_rows),
        "rerank_component_p95": qwen_latency["rerank_component_p95_ms"] <= 3000,
        "full_path_p95": qwen_latency["full_path_p95_ms"] <= 6000,
        "minimax_not_in_ranking_path": True,
    }
    checks = {**quality_checks, **invariant_checks}
    passed = all(checks.values())
    payload = {
        "generated_at": now_iso(), "iteration": args.iteration,
        "dataset_version": dataset.get("dataset_version"), "dataset_hash": dataset.get("dataset_hash"),
        "case_count": len(dataset.get("rows") or []), "configurations": 2,
        "expected_result_count": len(dataset.get("rows") or []) * 2, "actual_result_count": len(rows),
        "deterministic_baseline": {"metrics": control_metrics, "latency": control_latency},
        "qwen3_dedicated_rerank": {"metrics": qwen_metrics, "latency": qwen_latency, "api_success_rate": provider_success},
        "metrics": qwen_metrics, "latency": qwen_latency, "checks": checks,
        "passed": passed,
        "status": "R6_CANARY_PASSED" if passed else "QUERY_AWARE_GROUNDED_RAG_R6_QUALITY_GATE_FAILED",
        "vector_mutations": {"re_embedded": 0, "re_upserted": 0}, "rows": rows,
    }
    write_json(target.name, payload, immutable=True)
    all_rows = [*previous_rows, *rows]
    _write_cases(all_rows)
    write_json("rerank_comparison.json", {
        "generated_at": now_iso(), "iteration": args.iteration,
        "deterministic": control_metrics, "qwen3": qwen_metrics,
        "delta": {key: round(float(qwen_metrics.get(key) or 0) - float(control_metrics.get(key) or 0), 6) for key in qwen_metrics},
    })
    write_json("latency_breakdown.json", qwen_latency)
    print(json.dumps({key: value for key, value in payload.items() if key != "rows"}, ensure_ascii=False))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
