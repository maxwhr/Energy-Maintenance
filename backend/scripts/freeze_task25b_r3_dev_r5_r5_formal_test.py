from __future__ import annotations

import argparse
import hashlib
import json

from task25b_r3_dev_r5_r5_common import FORMAL_VERSION, OUT, now_iso, read_json, write_once


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--record-blocked",
        action="store_true",
        help="write the immutable zero-run lock when Canary did not pass",
    )
    args = parser.parse_args()
    canary = read_json("canary_result.json")
    dataset = OUT / "formal_test_dataset.json"
    canary_passed = bool(canary.get("passed"))

    if not canary_passed:
        if not args.record_blocked:
            print(json.dumps({
                "status": "NOT_FROZEN_CANARY_FAILED",
                "dataset_version": FORMAL_VERSION,
                "frozen": False,
            }))
            return 2
        payload = {
            "generated_at": now_iso(),
            "status": "NOT_EXECUTED_CANARY_FAILED",
            "canary_status": canary.get("status"),
            "created": False,
            "frozen": False,
            "dataset_version": None,
            "sha256": None,
            "formal_run_count": 0,
            "result": "NOT_EXECUTED_CANARY_FAILED",
        }
        write_once("formal_lock.json", payload)
        print(json.dumps(payload))
        return 0

    if not dataset.exists():
        raise SystemExit("passing Canary found, but formal test dataset is absent")
    raw = dataset.read_bytes()
    payload = {
        "generated_at": now_iso(),
        "status": "FROZEN",
        "created": True,
        "frozen": True,
        "dataset_version": FORMAL_VERSION,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "byte_count": len(raw),
        "formal_run_count": 0,
        "result": "NOT_EXECUTED",
    }
    write_once("formal_lock.json", payload)
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
