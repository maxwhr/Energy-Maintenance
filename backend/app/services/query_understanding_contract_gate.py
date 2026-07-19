from __future__ import annotations

from typing import Any


class QueryUnderstandingContractGate:
    """Pure gate evaluation shared by scripts, API summaries, and tests."""

    @staticmethod
    def evaluate(
        *,
        model_ab: dict[str, Any],
        context_merge: dict[str, Any],
        planner_probe: dict[str, Any],
        deterministic_rerank: dict[str, Any],
    ) -> dict[str, Any]:
        selected = str(model_ab.get("selected_runtime_model") or "deterministic")
        selected_metrics = (model_ab.get("models") or {}).get(selected) or {}
        checks = {
            "runtime_model_selected": selected != "deterministic",
            "structured_success": float(selected_metrics.get("structured_success_ratio") or 0.0) >= 0.95,
            "p95_ms": float((selected_metrics.get("latency_ms") or {}).get("p95") or 10**9) <= 4000.0,
            "intent_accuracy": float(selected_metrics.get("intent_accuracy") or 0.0) >= 0.95,
            "canonicalization_accuracy": float(selected_metrics.get("canonicalization_accuracy") or 0.0) >= 0.90,
            "hallucinated_models": int(selected_metrics.get("hallucinated_models") or 0) == 0,
            "hallucinated_alarms": int(selected_metrics.get("hallucinated_alarms") or 0) == 0,
            "context_merge": float(context_merge.get("accuracy") or 0.0) >= 0.95,
            "planner_probe": planner_probe.get("status") == "PASSED",
            "deterministic_rerank": deterministic_rerank.get("status") == "PASSED",
        }
        ready = all(checks.values())
        return {
            "status": "READY_FOR_CANARY" if ready else "QUERY_UNDERSTANDING_CONTRACT_NOT_READY",
            "ready": ready,
            "selected_runtime_model": selected,
            "checks": checks,
            "blockers": [key for key, passed in checks.items() if not passed],
        }
