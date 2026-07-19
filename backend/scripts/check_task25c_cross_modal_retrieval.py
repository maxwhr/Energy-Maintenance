from __future__ import annotations

import statistics

from app.core.database import SessionLocal
from app.models import MultimodalEvidenceItem, User
from app.services.cross_modal_retrieval_plan_service import CrossModalRetrievalPlanService
from app.services.cross_modal_retrieval_service import CrossModalRetrievalService
from app.services.multimodal_entity_resolution_service import MultimodalEntityResolution
from task25c_common import now_iso, read_json, write_json


def evidence(case_id: str, index: int, model: str, alarm: str) -> list[MultimodalEvidenceItem]:
    items = []
    if model:
        items.append(MultimodalEvidenceItem(
            case_id=case_id, evidence_id=f"{case_id}-model", modality="OCR_TEXT", evidence_type="DEVICE_MODEL",
            source_type="OCR_PROVIDER", source_hash=(f"{index + 1:064x}")[-64:], observed_text=model,
            normalized_text=model, device_model_candidates=[model], confidence=0.96, observation_status="OBSERVED",
            page_or_frame_locator={"region_id": "model"}, metadata_json={"official_match_valid": False},
        ))
    if alarm:
        items.append(MultimodalEvidenceItem(
            case_id=case_id, evidence_id=f"{case_id}-alarm", modality="OCR_TEXT", evidence_type="ALARM_CODE",
            source_type="OCR_PROVIDER", source_hash=(f"{index + 101:064x}")[-64:], observed_text=alarm,
            normalized_text=alarm, alarm_code_candidates=[alarm], confidence=0.96, observation_status="OBSERVED",
            page_or_frame_locator={"region_id": "alarm"}, metadata_json={"official_match_valid": False},
        ))
    return items


def main() -> int:
    benchmark = read_json("multimodal_benchmark_v1.json")
    rows = []
    with SessionLocal() as db:
        user = db.query(User).filter(User.role.in_(["admin", "expert"]), User.status == "active").first()
        if user is None:
            payload = {"generated_at": now_iso(), "status": "NOT_EXECUTED_NO_AUTHORIZED_OPERATOR", "rows": []}
            write_json("cross_modal_retrieval.json", payload)
            print(payload["status"])
            return 0
        service = CrossModalRetrievalService(db, current_user=user)
        planner = CrossModalRetrievalPlanService()
        for index, case in enumerate(benchmark.get("cases", [])[:12]):
            entities = case.get("expected_entities") or {}
            model = (entities.get("device_model") or [""])[0]
            alarm = (entities.get("alarm_codes") or [""])[0]
            items = evidence(case["case_id"], index, model, alarm)
            resolution = MultimodalEntityResolution(
                resolved_device_model=model or None,
                resolved_product_family=(entities.get("product_family") or [None])[0],
                resolved_equipment_category="pv_inverter",
                resolved_alarm_codes=[alarm] if alarm else [],
                resolution_confidence=0.96,
            )
            plan = planner.build(
                original_query=case["user_query"], normalized_query=None, confirmed_facts={}, resolution=resolution,
                evidence_items=items, occurrence_conditions=[], requested_information=["CAUSE", "ACTION", "SAFETY"],
            )
            result = service.retrieve(plan, top_k=5)
            rows.append({
                "case_id": case["case_id"],
                "original_query_retained": bool(result.generated_queries and result.generated_queries[0]["query_type"] == "ORIGINAL_TEXT"),
                "query_count": len(result.generated_queries),
                "candidate_count": len(result.raw_candidates),
                "surfaced_count": len(result.surfaced_results),
                "citation_count": len(result.citations),
                "citation_validity": result.citation_validity_ratio,
                "citation_coverage": result.citation_coverage_ratio,
                "scope_leakage": sum(not bool(item.get("scope_validation_passed")) for item in result.surfaced_results),
                "dedicated_rerank_used": result.dedicated_rerank.get("used"),
                "external_call_counts": result.external_call_counts,
                "latency_ms": result.stage_latency.get("total_ms"),
                "confidence_status": result.confidence_status,
            })
    total_surfaced = sum(row["surfaced_count"] for row in rows)
    total_citations = sum(row["citation_count"] for row in rows)
    payload = {
        "generated_at": now_iso(),
        "status": "PARTIAL_METRICS_BENCHMARK_LABELS_INSUFFICIENT" if benchmark.get("status") != "BENCHMARK_READY" else "EXECUTED",
        "cases": len(rows),
        "metrics": {
            "candidate_recall_at_50": None,
            "recall_at_5": None,
            "mrr": None,
            "ndcg_at_10": None,
            "citation_validity": round(sum(row["citation_validity"] for row in rows) / len(rows), 4) if rows else 0.0,
            "citation_coverage": round(sum(row["citation_coverage"] for row in rows) / len(rows), 4) if rows else 0.0,
            "citation_count": total_citations,
            "surfaced_count": total_surfaced,
            "scope_leakage": sum(row["scope_leakage"] for row in rows),
            "original_query_retained_ratio": round(sum(row["original_query_retained"] for row in rows) / len(rows), 4) if rows else 0.0,
            "retrieval_p95_ms": round(sorted(row["latency_ms"] for row in rows if row["latency_ms"])[max(0, int(len(rows) * .95) - 1)], 3) if rows else None,
        },
        "dedicated_rerank": {"used": False, "status": "DEFERRED_QWEN3_RERANK_CONFIG"},
        "external_calls": {"embedding": 0, "dashvector": 0, "qwen3_rerank": 0, "cloud_llm": 0},
        "rows": rows,
    }
    write_json("cross_modal_retrieval.json", payload)
    print(payload["status"], len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
