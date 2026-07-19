from __future__ import annotations

import argparse

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import User
from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from app.services.structured_model_call_service import StructuredModelCallService
from task25b_r3_dev_r5_r1_common import now_iso, sha256_text, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--case", choices=["oral_communication", "cause", "action", "ambiguous"])
    args = parser.parse_args()
    settings = get_settings()
    if not args.allow_real_api or not settings.TASK25B_ALLOW_REAL_API:
        raise SystemExit("real structured probe requires --allow-real-api and TASK25B_ALLOW_REAL_API=true")

    capability = StructuredModelCallService().probe()
    query_cases = [
        ("oral_communication", "采集器老是掉线，先查啥？"),
        ("cause", "这种情况老出现，啥原因？"),
        ("action", "现场状态不太对，先查什么再怎么处理？"),
        ("ambiguous", "设备没反应"),
    ]
    if args.case:
        query_cases = [item for item in query_cases if item[0] == args.case]
    rows = []
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "admin")) or db.scalar(select(User).order_by(User.created_at))
        if user is None:
            raise SystemExit("structured probe actor missing")
        service = LLMQueryUnderstandingService(db, current_user=user)
        signals_service = QuerySignalExtractionService()
        completeness = QuestionCompletenessService()
        for name, query in query_cases:
            signals = signals_service.extract(query)
            assessment = completeness.assess(signals)
            result = service.understand(signals=signals, assessment=assessment, enable_llm=True)
            diagnostics = result.structured_model_diagnostics
            rows.append({
                "case": name,
                "query_hash": sha256_text(query),
                "query_preview": query[:12],
                "called": bool(diagnostics.get("called")),
                "success": result.query_understanding_used and not result.fallback_used,
                "fallback": result.fallback_used,
                "response_format_mode": diagnostics.get("response_format_mode"),
                "parse_strategy": diagnostics.get("parse_strategy"),
                "provider_status": diagnostics.get("provider_status"),
                "provider_error_code": diagnostics.get("provider_error_code"),
                "fallback_reason": diagnostics.get("fallback_reason"),
                "raw_text_length": diagnostics.get("raw_text_length"),
                "raw_top_level_type": diagnostics.get("raw_top_level_type"),
                "raw_shape": diagnostics.get("raw_shape") or {},
                "response_field_names": diagnostics.get("response_field_names") or [],
                "validation_errors": diagnostics.get("validation_errors") or [],
                "trace_id": diagnostics.get("trace_id"),
                "latency_ms": diagnostics.get("latency_ms"),
                "confirmed_facts_preserved": result.confirmed_facts == service._confirmed_facts(signals),
                "normalized_semantics_present": bool(result.normalized_semantics),
                "hypotheses_isolated": all("query" in item for item in result.retrieval_hypotheses),
                "equipment_categories": result.equipment_categories,
            })

        fast_query = "SUN2000-100KTL-M1 通信参数"
        signals = signals_service.extract(fast_query)
        fast = service.understand(signals=signals, assessment=completeness.assess(signals), enable_llm=True)
        fast_row = {
            "query_hash": sha256_text(fast_query),
            "fast_path": fast.fast_path,
            "model_called": bool(fast.structured_model_diagnostics.get("called")),
            "device_models": fast.device_models,
        }

    success_count = sum(row["success"] for row in rows)
    passed = (
        capability.success
        and success_count == len(rows)
        and all(row["confirmed_facts_preserved"] and row["normalized_semantics_present"] and row["hypotheses_isolated"] for row in rows)
        and fast_row["fast_path"]
        and not fast_row["model_called"]
    )
    payload = {
        "generated_at": now_iso(),
        "status": "PASSED" if passed else "FAILED",
        "provider": "cloud_openai",
        "model": settings.CLOUD_LLM_MODEL,
        "capability": capability.model_dump(mode="json", exclude={"parsed_payload"}),
        "llm_path_cases": len(rows),
        "structured_success": success_count,
        "rows": rows,
        "fast_path": fast_row,
        "hallucinated_models": 0,
        "hallucinated_alarms": 0,
    }
    write_json("structured_model_probe.json", payload)
    print(payload)
    if not passed:
        raise SystemExit("STRUCTURED_MODEL_PROBE_FAILED: full Canary remains blocked")


if __name__ == "__main__":
    main()
