from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.services.llm_query_understanding_service import LLMQueryUnderstandingService  # noqa: E402
from app.services.minimax_resilience import MiniMaxCircuitBreaker  # noqa: E402
from app.services.query_signal_extraction_service import QuerySignalExtractionService  # noqa: E402
from app.services.question_completeness_service import QuestionCompletenessService  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".runtime" / "task25b_r3_dev_r5_r2_mm"
OUTPUT = RUNTIME / "query_understanding_probe.json"

CASES = [
    ("mm01", "通信老是掉线，啥原因", "MINIMAX_TOOL"),
    ("mm02", "机器没反应咋办", "MINIMAX_TOOL"),
    ("mm03", "晚上设备有时候不正常，怎么回事", "MINIMAX_TOOL"),
    ("mm04", "逆变器不对劲，先查什么再怎么处理", "MINIMAX_TOOL"),
    ("mm05", "设备老是自己断开，想知道原因和处理办法", "MINIMAX_TOOL"),
    ("mm06", "并网后没反应，是啥问题，要注意什么", "MINIMAX_TOOL"),
    ("mm07", "通信老是时好时坏，咋确认修好了", "MINIMAX_TOOL"),
    ("mm08", "最近机器老异常，原因和检查步骤都想知道", "MINIMAX_TOOL"),
    ("mm09", "夜间总掉线但白天正常，这是怎么回事", "MINIMAX_TOOL"),
    ("mm10", "风扇那边不正常，咋排查处理", "MINIMAX_TOOL"),
    ("mm11", "操作前要满足啥条件，还要注意哪些风险", "MINIMAX_TOOL"),
    ("mm12", "储能那边没反应但没报码，咋办", "MINIMAX_TOOL"),
    ("fast01", "SUN2000-100KTL-M1 如何检查通信", "FAST_PATH"),
    ("fast02", "告警 2031 如何处理", "FAST_PATH"),
    ("fast03", "SmartLogger3000 通信配置步骤", "FAST_PATH"),
    ("fast04", "检修操作的安全要求", "FAST_PATH"),
    ("det01", "通信中断原因分析", "DETERMINISTIC_NORMALIZATION"),
    ("det02", "过温故障处理步骤", "DETERMINISTIC_NORMALIZATION"),
    ("det03", "检修前置条件检查", "DETERMINISTIC_NORMALIZATION"),
    ("det04", "维修完成后的恢复验证", "DETERMINISTIC_NORMALIZATION"),
]


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * fraction + 0.999999)))
    return round(ordered[index], 3)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--diagnostic-one", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    model_probe = json.loads((RUNTIME / "minimax_model_probe.json").read_text(encoding="utf-8"))
    if not model_probe.get("passed"):
        payload = {"status": "BLOCKED_BY_MODEL_PROBE", "passed": False, "cases": 0}
        OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False))
        return 1
    if not args.allow_real_api or not settings.TASK25B_ALLOW_REAL_API:
        payload = {"status": "REAL_API_GUARD_CLOSED", "passed": False, "cases": 0}
        OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False))
        return 1
    if LLMQueryUnderstandingService._cache is not None:
        LLMQueryUnderstandingService._cache.clear()
    breaker = MiniMaxCircuitBreaker(cooldown_seconds=settings.MINIMAX_CIRCUIT_COOLDOWN_SECONDS)
    rows = []
    external_latencies: list[float] = []
    modes: dict[str, int] = {}
    structured_success = 0
    fact_preserved = 0
    hypothesis_isolated = 0
    normalized_nonempty = 0
    hallucinated_models = 0
    hallucinated_alarms = 0
    errors = 0
    selected_cases = CASES[:1] if args.diagnostic_one else CASES
    for case_id, query, expected_mode in selected_cases:
        signals = QuerySignalExtractionService().extract(query)
        assessment = QuestionCompletenessService().assess(signals)
        service = LLMQueryUnderstandingService(None, settings=settings, circuit_breaker=breaker)
        started = time.perf_counter()
        result = service.understand(
            signals=signals,
            assessment=assessment,
            enable_llm=expected_mode != "DETERMINISTIC_NORMALIZATION",
            allow_real_api=True,
        )
        elapsed = round((time.perf_counter() - started) * 1000, 3)
        mode = result.query_understanding_mode
        modes[mode] = modes.get(mode, 0) + 1
        structured = bool(result.structured_model_diagnostics.get("success"))
        if expected_mode == "MINIMAX_TOOL":
            external_latencies.append(elapsed)
            structured_success += int(mode == "MINIMAX_TOOL" and structured)
        expected_facts = LLMQueryUnderstandingService._confirmed_facts(signals)
        facts_ok = result.confirmed_facts == expected_facts
        fact_preserved += int(facts_ok)
        isolated = all(item.get("reason_code") and item.get("query") for item in result.retrieval_hypotheses)
        hypothesis_isolated += int(isolated)
        normalized_nonempty += int(any(result.normalized_semantics.values()))
        hallucinated_models += sum(value not in signals.device_models for value in result.device_models)
        hallucinated_alarms += sum(value not in signals.alarm_codes for value in result.alarm_codes)
        case_passed = mode == expected_mode and facts_ok and not result.provider_fallback
        if expected_mode != "MINIMAX_TOOL":
            case_passed = mode == expected_mode and facts_ok and not result.query_understanding_used
        errors += int(not case_passed)
        rows.append({
            "case_id": case_id,
            "query_hash": hashlib.sha256(query.encode("utf-8")).hexdigest(),
            "expected_mode": expected_mode,
            "actual_mode": mode,
            "external_call": bool(result.structured_model_diagnostics.get("called")),
            "structured_success": structured,
            "confirmed_facts_preserved": facts_ok,
            "hypotheses_isolated": isolated,
            "latency_ms": elapsed,
            "provider_status": result.structured_model_diagnostics.get("provider_status"),
            "provider_error_code": result.structured_model_diagnostics.get("provider_error_code"),
            "validation_errors": result.structured_model_diagnostics.get("validation_errors") or [],
            "response_field_names": result.structured_model_diagnostics.get("response_field_names") or [],
            "passed": case_passed,
        })
    if args.diagnostic_one:
        diagnostic = {
            "status": "DIAGNOSTIC_ONLY",
            "passed": False,
            "case_results": rows,
            "circuit_breaker": breaker.snapshot(),
        }
        diagnostic_output = RUNTIME / "query_understanding_probe_diagnostic.json"
        diagnostic_output.write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({
            "output": str(diagnostic_output.relative_to(ROOT)),
            "provider_status": rows[0]["provider_status"],
            "provider_error_code": rows[0]["provider_error_code"],
            "validation_errors": rows[0]["validation_errors"],
            "latency_ms": rows[0]["latency_ms"],
        }, ensure_ascii=False))
        return 0
    mm_cases = sum(expected == "MINIMAX_TOOL" for _, _, expected in CASES)
    success_ratio = structured_success / mm_cases
    p95 = percentile(external_latencies, 0.95)
    passed = all((
        len(CASES) >= 20,
        modes.get("MINIMAX_TOOL", 0) >= 12,
        modes.get("FAST_PATH", 0) >= 4,
        modes.get("DETERMINISTIC_NORMALIZATION", 0) >= 4,
        success_ratio >= 0.95,
        fact_preserved == len(CASES),
        hallucinated_models == 0,
        hallucinated_alarms == 0,
        hypothesis_isolated == len(CASES),
        p95 <= 4000,
        errors == 0,
    ))
    payload = {
        "task": "Task 25B-R3-DEV-R5-R2-MM query understanding probe",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASSED" if passed else "FAILED",
        "passed": passed,
        "cases": len(CASES),
        "mode_counts": modes,
        "minimax_tool_cases": mm_cases,
        "structured_success": structured_success,
        "structured_success_ratio": round(success_ratio, 4),
        "confirmed_facts_preservation_ratio": round(fact_preserved / len(CASES), 4),
        "normalized_semantics_nonempty_ratio": round(normalized_nonempty / len(CASES), 4),
        "hypothesis_isolation_ratio": round(hypothesis_isolated / len(CASES), 4),
        "hallucinated_models": hallucinated_models,
        "hallucinated_alarms": hallucinated_alarms,
        "error_count": errors,
        "latency_ms": {
            "p50": round(statistics.median(external_latencies), 3) if external_latencies else 0.0,
            "p95": p95,
        },
        "circuit_breaker": breaker.snapshot(),
        "case_results": rows,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)), "status": payload["status"], "modes": modes,
        "structured_success_ratio": payload["structured_success_ratio"], "p95_ms": p95, "errors": errors,
    }, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
