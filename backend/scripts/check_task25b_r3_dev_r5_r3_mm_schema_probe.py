from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from app.core.config import get_settings
from app.schemas.query_understanding import QueryUnderstandingV2Patch
from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.minimax_resilience import MiniMaxCircuitBreaker
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from task25b_r3_dev_r5_r3_mm_common import MODEL_AB_CASES, sha256_text, write_once


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if not args.allow_real_api or not settings.TASK25B_ALLOW_REAL_API:
        raise SystemExit("explicit real API authorization is required")
    if not settings.MINIMAX_ENABLED or not settings.MINIMAX_API_KEY:
        raise SystemExit("MiniMax configuration is incomplete")

    required = set(QueryUnderstandingV2Patch.model_json_schema()["required"])
    rows = []
    breaker = MiniMaxCircuitBreaker(cooldown_seconds=settings.MINIMAX_CIRCUIT_COOLDOWN_SECONDS)
    for case in MODEL_AB_CASES[:12]:
        signals = QuerySignalExtractionService().extract(case["query"])
        result = LLMQueryUnderstandingService(None, settings=settings, circuit_breaker=breaker).understand(
            signals=signals,
            assessment=QuestionCompletenessService().assess(signals),
            enable_llm=True,
            allow_real_api=True,
            model_override="MiniMax-M3",
            probe_mode=True,
            bypass_cache=True,
        )
        diag = result.structured_model_diagnostics or {}
        fields = set(diag.get("response_field_names") or [])
        row = {
            "case_id": case["id"],
            "query_hash": sha256_text(case["query"]),
            "structured_success": bool(diag.get("success")),
            "tool_use_success": int(diag.get("tool_call_count") or 0) == 1,
            "all_required_fields": fields == required,
            "unknown_fields": sorted(fields - required),
            "nested_retrieval_queries": "retrieval_queries" in fields or "retrieval_hypotheses" in fields,
            "provider_status": diag.get("provider_status"),
            "provider_error_code": diag.get("provider_error_code"),
            "latency_ms": float(diag.get("latency_ms") or 0.0),
            "attempt_count": int(diag.get("attempt_count") or 0),
        }
        row["passed"] = bool(
            row["structured_success"]
            and row["tool_use_success"]
            and row["all_required_fields"]
            and not row["unknown_fields"]
            and not row["nested_retrieval_queries"]
            and row["attempt_count"] == 1
        )
        rows.append(row)
        print(json.dumps({"case_id": row["case_id"], "passed": row["passed"], "latency_ms": row["latency_ms"]}))

    passed = sum(row["passed"] for row in rows)
    payload = {
        "task": "Task 25B-R3-DEV-R5-R3-MM schema probe",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": "MiniMax-M3",
        "schema_version": LLMQueryUnderstandingService.SCHEMA_VERSION,
        "tool_name": "submit_query_understanding_v2",
        "cases": len(rows),
        "passed_cases": passed,
        "tool_use_success": sum(row["tool_use_success"] for row in rows),
        "schema_valid": sum(row["all_required_fields"] and not row["unknown_fields"] for row in rows),
        "nested_retrieval_queries": sum(row["nested_retrieval_queries"] for row in rows),
        "status": "PASSED" if passed == len(rows) else "FAILED",
        "passed": passed == len(rows),
        "breaker": breaker.snapshot(),
        "rows": rows,
    }
    write_once("schema_probe.json", payload)
    print(json.dumps({"status": payload["status"], "passed": passed, "cases": len(rows)}))


if __name__ == "__main__":
    main()
