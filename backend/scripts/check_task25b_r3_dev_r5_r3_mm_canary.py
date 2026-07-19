from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from app.services.query_understanding_contract_gate import QueryUnderstandingContractGate
from task25b_r3_dev_r5_r3_mm_common import OUT, SOURCE_R5_R2, read_json, write_once


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--iteration", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    model_ab = read_json(OUT / "model_ab.json")
    context = read_json(OUT / "context_merge_probe.json")
    planner = read_json(OUT / "planner_probe.json")
    deterministic = read_json(SOURCE_R5_R2 / "deterministic_rerank_probe.json")
    gate = QueryUnderstandingContractGate.evaluate(
        model_ab=model_ab,
        context_merge=context,
        planner_probe=planner,
        deterministic_rerank=deterministic,
    )
    gate["generated_at"] = datetime.now(timezone.utc).isoformat()
    if not (OUT / "contract_gate.json").exists():
        write_once("contract_gate.json", gate)
    if not gate["ready"]:
        iteration = {
            "task": "Task 25B-R3-DEV-R5-R3-MM Canary",
            "dataset": "task25b_r3_dev_r5_r3_mm_train_dev_v1",
            "iteration": args.iteration,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "NOT_RUN_CONTRACT_NOT_READY",
            "executed": False,
            "case_count": 0,
            "real_query_calls": 0,
            "blockers": gate["blockers"],
            "passed": False,
        }
        write_once(f"canary_iteration_{args.iteration}.json", iteration)
        write_once("canary_result.json", {
            "status": "QUERY_UNDERSTANDING_CONTRACT_NOT_READY",
            "passed": False,
            "dataset": "task25b_r3_dev_r5_r3_mm_train_dev_v1",
            "required_cases": 60,
            "executed_cases": 0,
            "iterations_executed": 0,
            "blockers": gate["blockers"],
            "formal_test_allowed": False,
            "quality_metrics": {},
        })
        print(json.dumps({
            "status": iteration["status"], "iteration": args.iteration,
            "real_calls": 0, "blockers": gate["blockers"],
        }))
        return 2
    raise RuntimeError("Canary runner intentionally stops here until a future passing contract is reviewed")


if __name__ == "__main__":
    raise SystemExit(main())
