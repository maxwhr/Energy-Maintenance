from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from task25b_r3_dev_r5_r1_common import now_iso, write_json


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".runtime" / "task25b_r3_dev_r5_r1"


def read(name: str) -> dict:
    path = RUNTIME / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--iteration", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    structured = read("structured_model_probe.json")
    rerank = read("rerank_probe.json")
    raw = read("raw_vector_probe.json")
    prerequisites = {
        "structured_model_probe": structured.get("status") == "PASSED",
        "rerank_probe": rerank.get("status") == "PASSED" and rerank.get("structured_success") == 3,
        "raw_vector_probe": raw.get("status") == "PASSED",
    }
    if not all(prerequisites.values()):
        payload = {
            "generated_at": now_iso(), "iteration": args.iteration,
            "status": "BLOCKED_PRECANARY", "result": "QUERY_AWARE_GROUNDED_RAG_R1_QUALITY_GATE_FAILED",
            "prerequisites": prerequisites, "cases_executed": 0,
            "formal_test_allowed": False, "thresholds_lowered": False,
        }
        write_json("canary_result.json", payload)
        write_json(f"canary_iteration_{args.iteration}.json", payload)
        write_json("canary_case_results.json", {"status": "NOT_RUN_PRECANARY_BLOCKED", "items": []})
        with (RUNTIME / "canary_case_results.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            csv.writer(handle).writerow(["case_id", "query_hash", "category", "status"])
        print(payload)
        raise SystemExit(2)
    raise SystemExit("Canary runner is intentionally unavailable until all pre-Canary probes pass")


if __name__ == "__main__":
    main()
