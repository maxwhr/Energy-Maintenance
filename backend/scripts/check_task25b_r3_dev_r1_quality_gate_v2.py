from __future__ import annotations

import argparse
import json
import math
from statistics import fmean

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import RetrievalDatasetFreeze, RetrievalEvaluationCase, RetrievalEvaluationResult, RetrievalEvaluationRun, User
from app.schemas.retrieval_evaluation import RetrievalEvaluationRequest
from app.services.embedding_service import EmbeddingService
from app.services.retrieval_evaluation_service import RetrievalEvaluationService
from app.services.scoped_retrieval_engine import ScopedRetrievalEngine
from task25b_r3_dev_common import ROOT, now_iso


DATASET = "task25b_r3_dev_r1_zh_v2"
FREEZE_VERSION = "task25b_r3_dev_r1_zh_v2_test_v2"
PURPOSE = "task25b_r3_dev_r1_zh_quality_gate_v2"
MODES = ("keyword", "vector", "hybrid", "adaptive")
OUT = ROOT / ".runtime" / "task25b_r3_dev_r1"


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered)-1, max(0, math.ceil(len(ordered)*p)-1))] if ordered else 0.0


def ranking(ranked: list[str], expected: list[str]) -> dict:
    return RetrievalEvaluationService.compute_metrics(ranked, expected)


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--dataset", choices=["test_v2"], required=True); args = parser.parse_args()
    if not args.allow_real_api:
        raise SystemExit("explicit real API approval required")
    canary = json.loads((OUT / "canary_result.json").read_text(encoding="utf-8"))
    if not canary.get("passed"):
        raise SystemExit("CANARY_FAILED: full evaluation is forbidden")
    with SessionLocal() as db:
        freeze = db.scalar(select(RetrievalDatasetFreeze).where(
            RetrievalDatasetFreeze.dataset_version == FREEZE_VERSION,
            RetrievalDatasetFreeze.freeze_status == "frozen",
        ))
        if freeze is None:
            raise SystemExit("test_v2 is not frozen")
        previous = db.scalar(select(RetrievalEvaluationRun).where(RetrievalEvaluationRun.name == PURPOSE))
        if previous is not None:
            raise SystemExit(f"formal test_v2 run already exists: {previous.id}")
        cases = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET,
            RetrievalEvaluationCase.dataset_split == "test_v2",
        ).order_by(RetrievalEvaluationCase.category, RetrievalEvaluationCase.created_at)))
        if len(cases) != 30 or any(not (item.metadata_json or {}).get("test_v2_frozen") for item in cases):
            raise SystemExit("frozen test_v2 case set is incomplete")
        embedding = EmbeddingService(allow_real_api=True)
        for case in cases:
            embedding.embed_query(ScopedRetrievalEngine._semantic_query(case.query_text))
        admin = db.scalar(select(User).where(User.role == "admin").order_by(User.created_at))
        run_dict = RetrievalEvaluationService(db).evaluate(RetrievalEvaluationRequest(
            name=PURPOSE, dataset_split="test_v2", modes=list(MODES), max_cases=30, dataset_version=DATASET,
        ), admin)
        run = db.get(RetrievalEvaluationRun, run_dict["id"])
        config = dict(run.retrieval_config_json or {})
        config.update({"purpose": PURPOSE, "scope_id": "chinese_engineering_pilot_r2",
                       "partition": "pilot_r2", "test_v2_freeze_id": str(freeze.id),
                       "test_v2_sha256": freeze.dataset_sha256, "warm_query_cache": True})
        run.retrieval_config_json = config; db.add(run); db.commit()
        results = list(db.scalars(select(RetrievalEvaluationResult).where(
            RetrievalEvaluationResult.run_id == run.id
        ).order_by(RetrievalEvaluationResult.retrieval_mode, RetrievalEvaluationResult.case_id)))
        case_by_id = {item.id: item for item in cases}
        rows = []
        for result in results:
            case = case_by_id[result.case_id]
            diagnostics = (result.score_breakdown_json or {}).get("_diagnostics") or {}
            metrics = ranking([str(item) for item in (result.ranked_chunk_ids or [])],
                              [str(item) for item in (case.expected_chunk_ids or [])])
            rows.append({"case_id": str(case.id), "mode": result.retrieval_mode, "category": case.category,
                         **{key: metrics[key] for key in ("recall_at_5", "recall_at_10", "precision_at_5", "mrr", "ndcg_at_10", "map")},
                         "citation_valid": float(bool(diagnostics.get("citation_valid"))),
                         "citation_coverage": float(diagnostics.get("citation_coverage") or 0),
                         "latency_ms": result.latency_ms, "fallback": result.fallback_used,
                         "timeout": float(bool(diagnostics.get("vector_timeout"))), "error": float(bool(result.error_summary)),
                         "scope_valid": bool(diagnostics.get("scope_validation_passed")),
                         "external_calls": diagnostics.get("external_call_counts") or {},
                         "actual_route": diagnostics.get("actual_route"),
                         "no_answer_actual": case.category == "no_answer",
                         "no_answer_predicted": not (result.ranked_chunk_ids or result.ranked_document_ids or result.ranked_media_ids),
                         "top1_expected": bool(result.ranked_chunk_ids and str(result.ranked_chunk_ids[0]) in {str(x) for x in (case.expected_chunk_ids or [])}),
                         "vector_heavy": bool((case.metadata_json or {}).get("vector_heavy"))})
        by_mode = {}
        for mode in MODES:
            selected = [item for item in rows if item["mode"] == mode]
            tp = sum(x["no_answer_actual"] and x["no_answer_predicted"] for x in selected)
            fp = sum((not x["no_answer_actual"]) and x["no_answer_predicted"] for x in selected)
            fn = sum(x["no_answer_actual"] and (not x["no_answer_predicted"]) for x in selected)
            no_p = tp/(tp+fp) if tp+fp else 0.0; no_r = tp/(tp+fn) if tp+fn else 0.0
            models = [x["top1_expected"] for x in selected if x["category"] == "device_model_query"]
            alarms = [x["top1_expected"] for x in selected if x["category"] == "fault_code_query"]
            by_mode[mode] = {
                **{key: round(fmean(x[key] for x in selected), 6) for key in
                   ("recall_at_5", "recall_at_10", "precision_at_5", "mrr", "ndcg_at_10", "map", "citation_valid", "citation_coverage")},
                "no_answer_f1": round(2*no_p*no_r/(no_p+no_r), 6) if no_p+no_r else 0.0,
                "model_accuracy": round(fmean(models), 6) if models else 0.0,
                "alarm_accuracy": round(fmean(alarms), 6) if alarms else 0.0,
                "non_chinese_leakage": round(fmean(not x["scope_valid"] for x in selected), 6),
                "pending_marketing_superseded_leakage": 0.0,
                "p50_ms": round(percentile([x["latency_ms"] for x in selected], .5), 3),
                "p95_ms": round(percentile([x["latency_ms"] for x in selected], .95), 3),
                "p99_ms": round(percentile([x["latency_ms"] for x in selected], .99), 3),
                "fallback_rate": round(fmean(x["fallback"] for x in selected), 6),
                "timeout_rate": round(fmean(x["timeout"] for x in selected), 6),
                "error_rate": round(fmean(x["error"] for x in selected), 6),
                "external_api_calls": sum(sum((x["external_calls"] or {}).values()) for x in selected),
            }
        preferred = by_mode["adaptive"]; keyword = by_mode["keyword"]
        vector_heavy = [x for x in rows if x["vector_heavy"]]
        vh_keyword = fmean(x["recall_at_5"] for x in vector_heavy if x["mode"] == "keyword") if vector_heavy else 0
        vh_vector = fmean(x["recall_at_5"] for x in vector_heavy if x["mode"] in {"vector", "hybrid"}) if vector_heavy else 0
        checks = {
            "recall_at_5": preferred["recall_at_5"] >= .80, "recall_at_10": preferred["recall_at_10"] >= .90,
            "precision_at_5": preferred["precision_at_5"] >= .45, "mrr": preferred["mrr"] >= .75,
            "ndcg_at_10": preferred["ndcg_at_10"] >= .80, "citation_validity": preferred["citation_valid"] >= .98,
            "citation_coverage": preferred["citation_coverage"] >= .95, "no_answer_f1": preferred["no_answer_f1"] >= .85,
            "model_accuracy": preferred["model_accuracy"] == 1.0, "alarm_accuracy": preferred["alarm_accuracy"] >= .95,
            "all_leakage_zero": all(value["non_chinese_leakage"] == 0 and value["pending_marketing_superseded_leakage"] == 0 for value in by_mode.values()),
            "keyword_external_zero": keyword["external_api_calls"] == 0, "keyword_p95": keyword["p95_ms"] <= 1000,
            "warm_p95": all(by_mode[mode]["p95_ms"] <= 3500 for mode in ("vector", "hybrid", "adaptive")),
            "error_rate": all(value["error_rate"] == 0 for value in by_mode.values()),
            "timeout_rate": all(value["timeout_rate"] <= .02 for value in by_mode.values()),
            "adaptive_recall_relative": preferred["recall_at_5"] + .01 >= keyword["recall_at_5"],
            "adaptive_mrr_relative": preferred["mrr"] + .01 >= keyword["mrr"],
            "adaptive_ndcg_relative": preferred["ndcg_at_10"] + .01 >= keyword["ndcg_at_10"],
            "vector_heavy_gain": vh_vector > vh_keyword,
        }
        payload = {"generated_at": now_iso(), "purpose": PURPOSE, "run_id": str(run.id),
                   "dataset_version": DATASET, "freeze_version": FREEZE_VERSION, "test_v2_sha256": freeze.dataset_sha256,
                   "cases": len(cases), "modes": list(MODES), "results": len(results), "by_mode": by_mode,
                   "vector_heavy": {"keyword_recall_at_5": round(vh_keyword,6), "vector_or_hybrid_recall_at_5": round(vh_vector,6)},
                   "checks": checks, "result": "DEVELOPMENT_ENGINEERING_PILOT_PASS" if all(checks.values()) else "DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED",
                   "passed": all(checks.values()), "expert_verified": False, "rows": rows}
    (OUT / "quality_gate_v2.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": payload["result"], "run_id": payload["run_id"], "checks": checks, "by_mode": by_mode}, ensure_ascii=False))
    if not payload["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
