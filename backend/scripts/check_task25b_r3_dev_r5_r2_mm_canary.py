from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".runtime" / "task25b_r3_dev_r5_r2_mm"


def load(name: str) -> dict:
    path = RUNTIME / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(name: str, payload: dict | list) -> None:
    (RUNTIME / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--iteration", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    query = load("query_understanding_probe.json")
    deterministic = load("deterministic_rerank_probe.json")
    tiebreak = load("tiebreak_probe.json")
    blockers = []
    if not query.get("passed"):
        blockers.append("QUERY_UNDERSTANDING_PROBE_FAILED")
    if not deterministic.get("passed"):
        blockers.append("DETERMINISTIC_RERANK_PROBE_FAILED")
    if not args.allow_real_api:
        blockers.append("REAL_API_CLI_GUARD_CLOSED")
    if blockers:
        iteration = {
            "task": "Task 25B-R3-DEV-R5-R2-MM Canary",
            "dataset": "task25b_r3_dev_r5_r2_mm_train_dev_v1",
            "iteration": args.iteration,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "NOT_RUN_PRECONDITION_FAILED",
            "executed": False,
            "case_count": 0,
            "real_query_calls": 0,
            "real_tiebreak_calls": 0,
            "blockers": blockers,
            "quality_metrics": {},
            "passed": False,
        }
        write_json(f"canary_iteration_{args.iteration}.json", iteration)
        for number in (1, 2):
            path = RUNTIME / f"canary_iteration_{number}.json"
            if not path.exists():
                write_json(f"canary_iteration_{number}.json", {
                    **iteration,
                    "iteration": number,
                    "status": "NOT_RUN_PRECONDITION_FAILED",
                })
        result = {
            "status": "CANARY_NOT_RUN_QUERY_GATE_FAILED",
            "passed": False,
            "dataset": "task25b_r3_dev_r5_r2_mm_train_dev_v1",
            "required_cases": 60,
            "executed_cases": 0,
            "iterations_executed": 0,
            "blockers": blockers,
            "formal_test_allowed": False,
            "quality_metrics": {},
        }
        write_json("canary_result.json", result)
        write_json("canary_case_results.json", [])
        with (RUNTIME / "canary_case_results.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            csv.DictWriter(handle, fieldnames=["case_id", "status", "latency_ms", "notes"]).writeheader()
        write_json("latency_breakdown.json", {
            "status": "COMPONENT_PROBES_ONLY_CANARY_NOT_RUN",
            "fast_path_p95_ms": 0.0,
            "query_understanding_p95_ms": (query.get("latency_ms") or {}).get("p95"),
            "deterministic_rerank_p95_ms": (deterministic.get("latency_ms") or {}).get("p95"),
            "tiebreak_p95_ms": (tiebreak.get("latency_ms") or {}).get("p95"),
            "multi_query_p95_ms": None,
            "deep_path_p95_ms": None,
        })
        print(json.dumps({
            "iteration": args.iteration, "status": iteration["status"], "blockers": blockers,
            "real_calls": 0,
        }, ensure_ascii=False))
        return 1
    raise RuntimeError("Canary execution is not implemented because all preconditions unexpectedly passed")


if __name__ == "__main__":
    raise SystemExit(main())
