from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings
from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.minimax_resilience import MiniMaxCircuitBreaker
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from task25b_r3_dev_r5_r3_mm_common import MODEL_AB_CASES, OUT, safe_metrics, sha256_text, write_once


MODELS = ("MiniMax-M3", "MiniMax-M2.7-highspeed")


def normalize(value: str) -> str:
    return "".join(str(value or "").lower().split())


def run_model(model: str) -> tuple[dict, list[dict]]:
    settings = get_settings()
    breaker = MiniMaxCircuitBreaker(cooldown_seconds=settings.MINIMAX_CIRCUIT_COOLDOWN_SECONDS)
    rows = []
    for case in MODEL_AB_CASES:
        signals = QuerySignalExtractionService().extract(case["query"])
        result = LLMQueryUnderstandingService(None, settings=settings, circuit_breaker=breaker).understand(
            signals=signals,
            assessment=QuestionCompletenessService().assess(signals),
            enable_llm=True,
            allow_real_api=True,
            model_override=model,
            probe_mode=True,
            bypass_cache=True,
        )
        diag = result.structured_model_diagnostics or {}
        meta = diag.get("provider_response_meta") or {}
        token_usage = meta.get("token_usage") or {}
        contract = diag.get("model_contract_summary") or {}
        hallucinated_model = "hallucinated_canonical_fact_removed" in result.validation_errors and bool(
            QuerySignalExtractionService().extract(case["query"]).device_models
            != QuerySignalExtractionService().extract(result.canonical_question).device_models
        )
        hallucinated_alarm = "hallucinated_canonical_fact_removed" in result.validation_errors and not hallucinated_model
        structured_success = bool(diag.get("success"))
        canonical = normalize(result.canonical_question)
        canonical_correct = bool(
            structured_success
            and not hallucinated_model
            and not hallucinated_alarm
            and all(normalize(term) in canonical for term in case["terms"])
        )
        predicted_clarification = bool(contract.get("needs_clarification")) if structured_success else False
        row = {
            "case_id": case["id"],
            "query_hash": sha256_text(case["query"]),
            "structured_success": structured_success,
            "tool_use_success": int(diag.get("tool_call_count") or 0) == 1,
            "schema_valid": structured_success and not diag.get("validation_errors"),
            "intent_correct": structured_success and result.primary_intent == case["intent"],
            "canonicalization_correct": canonical_correct,
            "expected_clarification": bool(case["clarify"]),
            "predicted_clarification": predicted_clarification,
            "clarification_correct": predicted_clarification == bool(case["clarify"]),
            "hallucinated_models": int(hallucinated_model),
            "hallucinated_alarms": int(hallucinated_alarm),
            "latency_ms": float(diag.get("latency_ms") or 0.0),
            "prompt_tokens": token_usage.get("prompt_tokens"),
            "completion_tokens": token_usage.get("completion_tokens"),
            "total_tokens": token_usage.get("total_tokens"),
            "provider_status": diag.get("provider_status"),
            "provider_error_code": diag.get("provider_error_code"),
            "attempt_count": int(diag.get("attempt_count") or 0),
            "thinking_enabled": bool(meta.get("thinking_enabled")),
            "unexpected_thinking_block": bool(diag.get("unexpected_thinking_block")),
            "response_field_names": diag.get("response_field_names") or [],
        }
        rows.append(row)
        print(json.dumps({
            "model": model,
            "case_id": case["id"],
            "success": structured_success,
            "latency_ms": row["latency_ms"],
            "error": row["provider_error_code"],
        }))
    metrics = safe_metrics(rows)
    metrics.update({
        "model": model,
        "thinking_control": "disabled" if model == "MiniMax-M3" else "provider_mandatory",
        "thinking_enabled_observed": any(row["thinking_enabled"] for row in rows),
        "thinking_content_logged": False,
        "breaker": breaker.snapshot(),
    })
    return metrics, rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if not args.allow_real_api or not settings.TASK25B_ALLOW_REAL_API:
        raise SystemExit("explicit real API authorization is required")
    if not settings.MINIMAX_ENABLED or not settings.MINIMAX_API_KEY:
        raise SystemExit("MiniMax configuration is incomplete")
    if (OUT / "model_ab.json").exists():
        raise SystemExit("immutable complete model A/B already exists")

    models = {}
    rows_by_model = {}
    for model in MODELS:
        metrics, rows = run_model(model)
        models[model] = metrics
        rows_by_model[model] = rows

    passing = [model for model in MODELS if models[model]["passed"]]
    if passing:
        selected = min(passing, key=lambda name: models[name]["latency_ms"]["p95"])
        reason = "all hard gates passed; selected the passing model with lower p95"
    else:
        selected = "deterministic"
        reason = "neither candidate model passed every structured-quality and latency gate"
    payload = {
        "task": "Task 25B-R3-DEV-R5-R3-MM same-sample runtime model A/B",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": LLMQueryUnderstandingService.SCHEMA_VERSION,
        "tool_name": "submit_query_understanding_v2",
        "service_tier": "standard",
        "same_sample": True,
        "sample_count_per_model": len(MODEL_AB_CASES),
        "models_run_once": list(MODELS),
        "models": models,
        "rows_by_model": rows_by_model,
        "selected_runtime_model": selected,
        "selection_reason": reason,
        "contract_ready_from_model_ab": selected != "deterministic",
        "status": "PASSED" if selected != "deterministic" else "QUERY_UNDERSTANDING_CONTRACT_NOT_READY",
        "secret_exposure": False,
    }
    write_once("model_ab.json", payload)
    print(json.dumps({
        "status": payload["status"],
        "selected_runtime_model": selected,
        "models": {
            name: {
                "passed": value["passed"],
                "structured_success_ratio": value["structured_success_ratio"],
                "p95_ms": value["latency_ms"]["p95"],
            }
            for name, value in models.items()
        },
    }))


if __name__ == "__main__":
    main()
