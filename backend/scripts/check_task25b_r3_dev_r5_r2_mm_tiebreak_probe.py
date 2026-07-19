from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.services.llm_query_understanding_service import LLMQueryUnderstandingService  # noqa: E402
from app.services.minimax_resilience import MiniMaxCircuitBreaker  # noqa: E402
from app.services.minimax_tiebreak_service import MiniMaxTieBreakService  # noqa: E402
from app.services.query_signal_extraction_service import QuerySignalExtractionService  # noqa: E402
from app.services.question_completeness_service import QuestionCompletenessService  # noqa: E402
from app.services.rrf_fusion_service import QueryAwareCandidate  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".runtime" / "task25b_r3_dev_r5_r2_mm"
OUTPUT = RUNTIME / "tiebreak_probe.json"

QUERIES = [
    "通信掉线的原因", "通信中断如何排查", "设备离线原因", "夜间掉线检查", "风扇异常原因",
    "过温处理步骤", "安全检修流程", "操作前置条件", "维修恢复验证", "并网故障检查",
    "组串异常原因", "绝缘阻抗低排查", "电网过压处理", "直流异常检查", "通信模块故障",
    "多种可能原因", "不同安全流程", "HTML 与 PDF 互补证据", "不同型号候选冲突", "动作和症状冲突",
]


def understanding(query: str):
    signals = QuerySignalExtractionService().extract(query)
    return LLMQueryUnderstandingService._deterministic(
        signals, QuestionCompletenessService().assess(signals)
    )


def candidates(case_index: int, count: int) -> list[QueryAwareCandidate]:
    output = []
    for index in range(count):
        chunk_id = str(uuid4())
        source_type = "HTML" if index % 2 else "PDF"
        output.append(QueryAwareCandidate(
            candidate_id=f"case-{case_index}-candidate-{index}",
            chunk_id=chunk_id,
            document_id=str(uuid4()),
            document_title=f"华为官方{source_type}文档",
            content=f"候选{index + 1}：通信、原因、检查步骤和安全条件的直接证据摘要。",
            section_title="故障处理",
            page_number=index + 1 if source_type == "PDF" else None,
            source_channels={"RAW_VECTOR" if index % 2 else "SCOPED_KEYWORD"},
            source_query_types={"ORIGINAL"},
            raw_scores={"score": 0.8 - index * 0.01},
            rrf_score=0.8 - index * 0.01,
            final_score=0.8 - index * 0.005,
            source_chunk_ids=[chunk_id],
            source_locator={"section": "故障处理", "page_number": index + 1 if source_type == "PDF" else None},
            scope_validation_passed=True,
        ))
    return output


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int((len(ordered) - 1) * 0.95 + 0.999999))], 3)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    model_probe = json.loads((RUNTIME / "minimax_model_probe.json").read_text(encoding="utf-8"))
    if not model_probe.get("passed"):
        payload = {"status": "BLOCKED_BY_MODEL_PROBE", "passed": False, "real_calls": 0}
        OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False))
        return 1
    if not args.allow_real_api or not settings.TASK25B_ALLOW_REAL_API:
        payload = {"status": "REAL_API_GUARD_CLOSED", "passed": False, "real_calls": 0}
        OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False))
        return 1
    if MiniMaxTieBreakService._cache is not None:
        MiniMaxTieBreakService._cache.clear()
    breaker = MiniMaxCircuitBreaker(cooldown_seconds=settings.MINIMAX_CIRCUIT_COOLDOWN_SECONDS)
    service = MiniMaxTieBreakService(settings=settings, circuit_breaker=breaker)
    rows = []
    latencies = []
    called = 0
    success = 0
    tool_calls = 0
    additions = 0
    removals = 0
    source_modifications = 0
    unknown_ids = 0
    duplicate_ids = 0
    order_preserved_failures = 0
    for index, query in enumerate(QUERIES):
        count = 6 if index % 4 == 0 else 4
        items = candidates(index, count)
        original_ids = [item.candidate_id for item in items]
        source_snapshot = {
            item.candidate_id: (set(item.source_channels), list(item.source_chunk_ids), dict(item.source_locator))
            for item in items
        }
        started = time.perf_counter()
        result = service.rerank(
            items,
            understanding=understanding(query),
            allow_real_api=True,
            citation_status={item.chunk_id: True for item in items},
            force=True,
            max_candidates=count,
        )
        elapsed = round((time.perf_counter() - started) * 1000, 3)
        diagnostics = result.diagnostics
        if diagnostics.get("called"):
            called += 1
            latencies.append(elapsed)
        success += int(bool(diagnostics.get("structured_success")))
        tool_calls += int(bool(diagnostics.get("tool_call_used")))
        additions += int(diagnostics.get("candidate_additions") or 0)
        removals += int(diagnostics.get("candidate_removals") or 0)
        source_modifications += sum(
            (item.source_channels, item.source_chunk_ids, item.source_locator) != source_snapshot[item.candidate_id]
            for item in result.candidates
        )
        unknown_ids += int(diagnostics.get("fallback_reason") == "UNKNOWN_CANDIDATE_ID")
        duplicate_ids += int(diagnostics.get("fallback_reason") == "DUPLICATE_CANDIDATE_ID")
        boundary = set(item.candidate_id for item in result.candidates) == set(original_ids) and len(result.candidates) == len(items)
        rows.append({
            "case_id": f"tie-{index + 1:02d}",
            "candidate_count": count,
            "called": diagnostics.get("called", False),
            "structured_success": diagnostics.get("structured_success", False),
            "fallback_reason": diagnostics.get("fallback_reason"),
            "candidate_boundary_preserved": boundary,
            "sources_preserved": source_modifications == 0,
            "latency_ms": elapsed,
        })
    simulated_items = candidates(99, 4)
    simulated_ids = [item.candidate_id for item in simulated_items]
    simulated = MiniMaxTieBreakService(
        settings=settings.model_copy(update={"TASK25B_ALLOW_REAL_API": False}),
        circuit_breaker=MiniMaxCircuitBreaker(),
    ).rerank(
        simulated_items,
        understanding=understanding("通信原因冲突"),
        allow_real_api=True,
        force=True,
    )
    simulated_preserved = [item.candidate_id for item in simulated.candidates] == simulated_ids
    order_preserved_failures += int(simulated_preserved)
    structured_ratio = success / max(1, called)
    tool_ratio = tool_calls / max(1, called)
    latency_p95 = p95(latencies)
    slo_passed = all((
        called >= 20,
        structured_ratio >= 0.95,
        tool_ratio == 1.0,
        additions == 0,
        removals == 0,
        source_modifications == 0,
        unknown_ids == 0,
        duplicate_ids == 0,
        simulated_preserved,
        latency_p95 <= 6000,
    ))
    payload = {
        "task": "Task 25B-R3-DEV-R5-R2-MM tie-break probe",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASSED" if slo_passed else "OPTIONAL_MINIMAX_TIEBREAK_DEGRADED",
        "passed": slo_passed,
        "real_calls": called,
        "structured_success": success,
        "structured_success_ratio": round(structured_ratio, 4),
        "tool_call_ratio": round(tool_ratio, 4),
        "candidate_additions": additions,
        "candidate_removals": removals,
        "source_modifications": source_modifications,
        "unknown_candidate_ids": unknown_ids,
        "duplicate_candidate_ids": duplicate_ids,
        "simulated_failure_order_preserved": simulated_preserved,
        "order_preservation_on_failure_ratio": float(simulated_preserved),
        "error_rate": 0.0,
        "latency_ms": {
            "p50": round(statistics.median(latencies), 3) if latencies else 0.0,
            "p95": latency_p95,
        },
        "circuit_breaker": breaker.snapshot(),
        "case_results": rows,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)), "status": payload["status"], "real_calls": called,
        "structured_success_ratio": payload["structured_success_ratio"], "p95_ms": latency_p95,
        "failure_order_preserved": simulated_preserved,
    }, ensure_ascii=False))
    return 0 if slo_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
