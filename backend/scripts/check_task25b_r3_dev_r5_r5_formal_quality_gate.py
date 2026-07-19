from __future__ import annotations

import argparse
import json

from task25b_r3_dev_r5_r5_common import FORMAL_VERSION, OUT, read_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    canary = read_json("canary_result.json")
    formal_lock = OUT / "formal_lock.json"
    dataset = OUT / "formal_test_dataset.json"

    if not bool(canary.get("passed")):
        print(json.dumps({
            "status": "NOT_RUN_CANARY_FAILED",
            "dataset_version": FORMAL_VERSION,
            "run_count": 0,
            "passed": False,
        }))
        return 2
    if not formal_lock.exists() or not dataset.exists():
        print(json.dumps({
            "status": "NOT_RUN_FORMAL_NOT_FROZEN",
            "dataset_version": FORMAL_VERSION,
            "run_count": 0,
            "passed": False,
        }))
        return 2
    lock = read_json(formal_lock)
    if not lock.get("frozen"):
        raise SystemExit("formal test lock is not frozen")
    if int(lock.get("formal_run_count") or 0) != 0:
        raise SystemExit("formal blind test has already been executed; a second run is forbidden")
    if not args.allow_real_api:
        raise SystemExit("formal quality gate requires explicit --allow-real-api")
    raise SystemExit("formal blind runner is unavailable without an approved disjoint formal dataset")


if __name__ == "__main__":
    raise SystemExit(main())
