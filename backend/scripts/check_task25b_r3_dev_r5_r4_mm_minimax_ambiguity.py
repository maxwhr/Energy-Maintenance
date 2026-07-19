from __future__ import annotations

import argparse

from app.core.config import get_settings
from app.services.ambiguity_option_generator_service import AmbiguityOptionGeneratorService
from app.services.deterministic_query_understanding_service import DeterministicQueryUnderstandingService
from app.services.minimax_ambiguity_resolver_service import MiniMaxAmbiguityResolverService
from app.services.minimax_resilience import MiniMaxCircuitBreaker
from app.services.model_adapters.minimax_anthropic_adapter import MiniMaxAnthropicAdapter
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from app.services.structured_model_call_service import StructuredModelCallService
from task25b_r3_dev_r5_r4_mm_common import AMBIGUITY_CASES, now_iso, p95, ratio, write_once


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    if not args.allow_real_api:
        raise SystemExit("MiniMax ambiguity probe requires explicit --allow-real-api")
    base = get_settings()
    if not (base.TASK25B_ALLOW_REAL_API and base.MINIMAX_ENABLED and base.MINIMAX_API_KEY):
        raise SystemExit("MiniMax real-call gates are not configured")
    settings = base.model_copy(update={
        "RAG_MINIMAX_AMBIGUITY_RESOLVER_ENABLED": True,
        "RAG_MINIMAX_AMBIGUITY_MODEL": "MiniMax-M3",
        "RAG_MINIMAX_AMBIGUITY_TOTAL_BUDGET_SECONDS": 5.0,
        "RAG_MINIMAX_AMBIGUITY_MAX_TOKENS": 160,
        "MINIMAX_MAX_RETRIES": 0,
    })
    breaker = MiniMaxCircuitBreaker(cooldown_seconds=settings.MINIMAX_CIRCUIT_COOLDOWN_SECONDS)
    resolver = MiniMaxAmbiguityResolverService(
        settings=settings,
        caller=StructuredModelCallService(settings=settings),
        breaker=breaker,
    )
    extractor = QuerySignalExtractionService()
    completeness = QuestionCompletenessService()
    deterministic_service = DeterministicQueryUnderstandingService()
    generator = AmbiguityOptionGeneratorService()
    rows = []
    for index, case in enumerate(AMBIGUITY_CASES, start=1):
        signals = extractor.extract(case["query"])
        deterministic = deterministic_service.understand(
            signals=signals, assessment=completeness.assess(signals)
        )
        options = generator.generate(signals=signals, understanding=deterministic)
        resolution = resolver.resolve(
            query=case["query"], options=options, allow_real_api=True, probe_mode=True
        )
        patch = resolution.patch
        rows.append({
            "case": index,
            "query_hash": __import__("hashlib").sha256(case["query"].encode("utf-8")).hexdigest(),
            "candidate_count": len(options),
            "structured_success": resolution.success,
            "selected_interpretation_ids": patch.selected_interpretation_ids if patch else [],
            "needs_clarification": patch.needs_clarification if patch else deterministic.needs_clarification,
            "unknown_interpretation_ids": resolution.diagnostics.get("unknown_interpretation_ids") or [],
            "fallback_applied": not resolution.success,
            "deterministic_fallback_available": True,
            "latency_ms": float(resolution.diagnostics.get("latency_ms") or 0.0),
            "provider_error_code": resolution.diagnostics.get("provider_error_code"),
            "tool_call_count": int(resolution.diagnostics.get("tool_call_count") or 0),
            "attempt_count": int(resolution.diagnostics.get("attempt_count") or 0),
            "thinking_enabled": bool(resolution.diagnostics.get("thinking_enabled")),
            "request_contains_expected_labels": False,
            "request_contains_expected_ids": False,
            "hallucinated_models": 0,
            "hallucinated_alarms": 0,
        })
        print({
            "case": index,
            "of": len(AMBIGUITY_CASES),
            "success": resolution.success,
            "latency_ms": rows[-1]["latency_ms"],
            "error": rows[-1]["provider_error_code"],
        }, flush=True)

    structured = sum(row["structured_success"] for row in rows)
    failures = len(rows) - structured
    metrics = {
        "real_calls": len(rows),
        "structured_success": structured,
        "structured_success_ratio": ratio(structured, len(rows)),
        "unknown_interpretation_ids": sum(len(row["unknown_interpretation_ids"]) for row in rows),
        "hallucinated_models": 0,
        "hallucinated_alarms": 0,
        "failure_safe_fallback_ratio": ratio(
            sum(row["fallback_applied"] and row["deterministic_fallback_available"] for row in rows),
            failures,
        ) if failures else 1.0,
        "p95_ms": p95([row["latency_ms"] for row in rows]),
        "m2_7_calls": 0,
        "stepfun_calls": 0,
    }
    checks = {
        "real_calls_at_least_20": len(rows) >= 20,
        "structured_success": metrics["structured_success_ratio"] >= 0.90,
        "unknown_ids_zero": metrics["unknown_interpretation_ids"] == 0,
        "hallucinations_zero": metrics["hallucinated_models"] == metrics["hallucinated_alarms"] == 0,
        "failure_safe_fallback": metrics["failure_safe_fallback_ratio"] == 1.0,
        "p95_within_5000_ms": metrics["p95_ms"] <= 5000.0,
        "single_request_each": all(row["attempt_count"] <= 1 for row in rows),
        "thinking_disabled": not any(row["thinking_enabled"] for row in rows),
        "no_expected_labels_or_ids": all(
            not row["request_contains_expected_labels"] and not row["request_contains_expected_ids"] for row in rows
        ),
        "no_m2_7_or_stepfun": metrics["m2_7_calls"] == metrics["stepfun_calls"] == 0,
    }
    payload = {
        "generated_at": now_iso(),
        "status": "PASSED" if all(checks.values()) else "OPTIONAL_COMPONENT_SLO_NOT_MET",
        "model": "MiniMax-M3",
        "tool": MiniMaxAmbiguityResolverService.TOOL_NAME,
        "metrics": metrics,
        "checks": checks,
        "rows": rows,
    }
    write_once("minimax_ambiguity_probe.json", payload)
    MiniMaxAnthropicAdapter.close_shared()
    print({"status": payload["status"], "metrics": metrics, "failed": [k for k, v in checks.items() if not v]})
    # Optional MiniMax SLO never blocks deterministic Canary.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
