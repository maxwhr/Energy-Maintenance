from __future__ import annotations

import argparse
import json

from task25b_r3_dev_r5_r6_common import FORMAL_VERSION, OUT


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    canary = OUT / "canary_iteration_2.json"
    if not canary.is_file() or not json.loads(canary.read_text(encoding="utf-8")).get("passed"):
        print(json.dumps({
            "status": "NOT_RUN_CANARY_FAILED", "dataset_version": FORMAL_VERSION,
            "run_count": 0, "passed": False,
        }))
        return 2
    lock = OUT / "formal_lock.json"
    dataset = OUT / "formal_test_dataset.json"
    if not lock.is_file() or not dataset.is_file():
        print(json.dumps({"status": "NOT_RUN_FORMAL_NOT_FROZEN", "run_count": 0, "passed": False}))
        return 2
    frozen = json.loads(lock.read_text(encoding="utf-8"))
    if not frozen.get("frozen") or int(frozen.get("formal_run_count") or 0) != 0:
        raise SystemExit("formal dataset must be frozen and unused")
    if not args.allow_real_api:
        raise SystemExit("formal gate requires explicit --allow-real-api")
    raise SystemExit("formal runner requires the approved disjoint dataset evaluator; no run was consumed")


if __name__ == "__main__":
    raise SystemExit(main())
