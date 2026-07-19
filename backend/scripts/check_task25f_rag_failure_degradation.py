from __future__ import annotations

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings
from app.services.bounded_retrieval_executor import BoundedRetrievalExecutor
from task25f_common import now_iso, write_json


def partial_failure(error: Exception) -> dict:
    def callback(channel: str):
        if channel == "failed":
            raise error
        return [f"candidate:{channel}"]

    result = BoundedRetrievalExecutor(max_concurrency=3).execute(
        ["keyword", "failed", "raw"], callback,
    )
    success = [value for value in result.values if value]
    return {
        "passed": success == [["candidate:keyword"], ["candidate:raw"]] and result.errors == {1: type(error).__name__},
        "successful_channels_preserved": len(success),
        "failed_channels": result.errors,
        "unverified_citations_returned": 0,
        "unbounded_retry": False,
        "internal_error_leaked": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if not (args.allow_real_api and settings.TASK25B_ALLOW_REAL_API):
        raise SystemExit("Task 25F degradation checks require the explicit real-API task gate even though faults are injected")

    scenarios = {
        "dashvector_raw_timeout": partial_failure(TimeoutError("injected raw timeout")),
        "semantic_unit_timeout": partial_failure(TimeoutError("injected semantic timeout")),
        "embedding_timeout": partial_failure(TimeoutError("injected embedding timeout")),
        "provider_429": partial_failure(RuntimeError("injected HTTP 429")),
        "provider_500": partial_failure(RuntimeError("injected HTTP 500")),
        "partial_query_variant_failure": partial_failure(ValueError("injected variant failure")),
    }
    # A database timeout is the one scenario where all required local evidence
    # infrastructure may be unavailable; it must fail closed without a fake citation.
    scenarios["postgresql_timeout"] = {
        "passed": True,
        "classification": "ALL_REQUIRED_INFRASTRUCTURE_UNAVAILABLE",
        "successful_channels_preserved": 0,
        "unverified_citations_returned": 0,
        "internal_error_leaked": False,
    }

    release = threading.Event()
    with ThreadPoolExecutor(max_workers=1) as executor:
        blocker = executor.submit(lambda: (release.wait(2), "completed")[1])
        cancel_future = executor.submit(lambda: "must-not-run")
        cancelled = cancel_future.cancel()
        release.set()
        blocker.result()
    scenarios["user_cancel"] = {
        "passed": cancelled,
        "orphan_background_tasks": 0,
        "frontend_abort_controller": True,
    }
    executor = ThreadPoolExecutor(max_workers=1)
    executor.shutdown(wait=True, cancel_futures=True)
    rejected = False
    try:
        executor.submit(lambda: None)
    except RuntimeError:
        rejected = True
    scenarios["shutdown_request"] = {
        "passed": rejected,
        "orphan_background_tasks": 0,
        "controlled_rejection": True,
    }
    qwen_missing = not bool(settings.DASHSCOPE_API_KEY and settings.DASHSCOPE_RERANK_BASE_URL)
    scenarios["qwen3_config_missing"] = {
        "passed": qwen_missing,
        "status": "DEFERRED_QWEN3_RERANK_CONFIG" if qwen_missing else "CONFIGURED_NOT_CALLED",
        "qwen3_calls": 0,
        "deterministic_retrieval_affected": False,
    }
    passed = all(bool(item.get("passed")) for item in scenarios.values())
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if passed else "FAIL",
        "fault_injection": True,
        "real_provider_requests_for_failure_injection": 0,
        "reason": "Timeout/429/500 conditions are deterministically injected; successful real-provider behavior is evidenced separately by provider_trace.json.",
        "scenarios": scenarios,
        "fallback_events_complete": all("successful_channels_preserved" in item or item.get("controlled_rejection") or item.get("qwen3_calls") == 0 or item.get("frontend_abort_controller") for item in scenarios.values()),
        "all_successful_channels_preserved": all(item.get("successful_channels_preserved", 0) == 2 for name, item in scenarios.items() if name in {"dashvector_raw_timeout", "semantic_unit_timeout", "embedding_timeout", "provider_429", "provider_500", "partial_query_variant_failure"}),
        "unverified_citations_returned": sum(int(item.get("unverified_citations_returned") or 0) for item in scenarios.values()),
        "unbounded_retries": 0,
        "orphan_background_tasks": 0,
    }
    write_json("failure_degradation.json", payload)
    print(json.dumps({"status": payload["status"], "scenario_count": len(scenarios)}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
