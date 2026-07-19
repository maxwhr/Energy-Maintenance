from __future__ import annotations

import argparse
import json

from task25b_r3_dev_r5_r3_mm_common import OUT, read_json, write_once


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.parse_args()
    status = read_json(OUT / "formal_test_status.json")
    if not status.get("formal_test_allowed"):
        payload = {
            "status": "NOT_RUN_CONTRACT_OR_CANARY_NOT_PASSED",
            "run_count": 0,
            "dataset": None,
            "passed": False,
        }
        write_once("formal_quality_gate.json", payload)
        print(json.dumps(payload))
        return 2
    raise RuntimeError("formal quality gate requires a frozen formal dataset")


if __name__ == "__main__":
    raise SystemExit(main())
