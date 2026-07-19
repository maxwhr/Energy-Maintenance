from __future__ import annotations

import argparse
import json

from task25b_r3_dev_r5_r4_mm_common import FORMAL_VERSION, OUT, read_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    canary = read_json("canary_result.json")
    deterministic_passed = bool((canary.get("deterministic_only") or {}).get("passed"))
    frozen = OUT / "formal_test_freeze.json"
    if not deterministic_passed or not frozen.exists():
        print(json.dumps({
            "status": "NOT_RUN_DETERMINISTIC_CANARY_FAILED_OR_FORMAL_NOT_FROZEN",
            "dataset_version": FORMAL_VERSION,
            "run_count": 0,
            "passed": False,
        }))
        return 2
    if not args.allow_real_api:
        raise SystemExit("formal quality gate requires explicit --allow-real-api")
    if (OUT / "formal_quality_gate.json").exists():
        raise SystemExit("formal blind test has already been executed; a second run is forbidden")
    raise SystemExit("formal blind runner is unavailable because no approved frozen formal dataset was created")


if __name__ == "__main__":
    raise SystemExit(main())
