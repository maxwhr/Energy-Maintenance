from __future__ import annotations

import hashlib
import json

from task25b_r3_dev_r5_r4_mm_common import FORMAL_VERSION, OUT, read_json, write_once


def main() -> int:
    canary = read_json("canary_result.json")
    dataset = OUT / "formal_test_dataset.json"
    if not bool((canary.get("deterministic_only") or {}).get("passed")) or not dataset.exists():
        print(json.dumps({
            "status": "NOT_FROZEN_DETERMINISTIC_CANARY_FAILED_OR_DATASET_ABSENT",
            "dataset_version": FORMAL_VERSION,
            "frozen": False,
        }))
        return 2
    raw = dataset.read_bytes()
    payload = {
        "status": "FROZEN",
        "dataset_version": FORMAL_VERSION,
        "frozen": True,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "byte_count": len(raw),
        "formal_run_count": 0,
    }
    write_once("formal_test_freeze.json", payload)
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
