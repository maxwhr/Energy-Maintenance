from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".runtime" / "task25b_r3_dev_r5_r2_mm"
OUTPUT = RUNTIME / "provider_ab_result.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def ratio(value: dict, numerator: str, denominator: str) -> float | None:
    total = int(value.get(denominator) or 0)
    return round(int(value.get(numerator) or 0) / total, 4) if total else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.parse_args()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    minimax_query = load(RUNTIME / "query_understanding_probe.json")
    minimax_tie = load(RUNTIME / "tiebreak_probe.json")
    stepfun_query = load(ROOT / ".runtime" / "task25b_r3_dev_r5_r1" / "structured_model_probe.json")
    stepfun_rerank = load(ROOT / ".runtime" / "task25b_r3_dev_r5_r1" / "rerank_probe.json")
    payload = {
        "task": "Task 25B-R3-DEV-R5-R2-MM provider offline A/B",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "RECORDED_FROM_REAL_PROBES_QUERY_GATE_FAILED",
        "same_request_provider_chain": False,
        "same_sample_ab_executed": False,
        "same_sample_ab_blocked_reason": "MINIMAX_QUERY_UNDERSTANDING_GATE_FAILED",
        "methodology": "Current MiniMax real probes compared with frozen R5-R1 StepFun real probes; not scored as same-sample A/B.",
        "minimax": {
            "query_cases": minimax_query.get("minimax_tool_cases", 0),
            "query_structured_success": minimax_query.get("structured_success", 0),
            "query_success_ratio": minimax_query.get("structured_success_ratio"),
            "query_p95_ms": (minimax_query.get("latency_ms") or {}).get("p95"),
            "tiebreak_cases": minimax_tie.get("real_calls", 0),
            "tiebreak_structured_success": minimax_tie.get("structured_success", 0),
            "tiebreak_success_ratio": minimax_tie.get("structured_success_ratio"),
            "tiebreak_p95_ms": (minimax_tie.get("latency_ms") or {}).get("p95"),
            "candidate_boundary": minimax_tie.get("candidate_additions", 0) == 0 and minimax_tie.get("candidate_removals", 0) == 0,
        },
        "stepfun_frozen_r5_r1": {
            "query_cases": stepfun_query.get("cases", 0),
            "query_structured_success": stepfun_query.get("success", 0),
            "query_success_ratio": ratio(stepfun_query, "success", "cases"),
            "query_p95_ms": (stepfun_query.get("latency_ms") or {}).get("p95"),
            "rerank_cases": stepfun_rerank.get("cases", 0),
            "rerank_structured_success": stepfun_rerank.get("structured_success", 0),
            "rerank_success_ratio": ratio(stepfun_rerank, "structured_success", "cases"),
            "rerank_p95_ms": (stepfun_rerank.get("latency_ms") or {}).get("p95"),
        },
        "selected_query_provider": "deterministic_safe_fallback",
        "selected_primary_reranker": "deterministic_evidence_rerank",
        "selected_optional_tiebreak_provider": "minimax_degraded",
        "request_level_chaining": False,
        "passed": False,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT.relative_to(ROOT)), "status": payload["status"],
        "request_level_chaining": False, "selected_primary_reranker": payload["selected_primary_reranker"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
