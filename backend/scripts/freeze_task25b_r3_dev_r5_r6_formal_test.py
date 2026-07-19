from __future__ import annotations

import hashlib
import json

from task25b_r3_dev_r5_r6_common import FORMAL_VERSION, OUT, now_iso, write_json


def main() -> int:
    canary_path = OUT / "canary_iteration_2.json"
    dataset = OUT / "formal_test_dataset.json"
    canary_passed = canary_path.is_file() and bool(json.loads(canary_path.read_text(encoding="utf-8")).get("passed"))
    if not canary_passed:
        print(json.dumps({"status": "NOT_FROZEN_CANARY_FAILED", "dataset_version": FORMAL_VERSION, "frozen": False}))
        return 2
    if not dataset.is_file():
        raise SystemExit("passing Canary found, but the approved disjoint formal dataset is absent")
    payload = json.loads(dataset.read_text(encoding="utf-8"))
    if int(payload.get("case_count") or len(payload.get("rows") or [])) < 100:
        raise SystemExit("formal dataset must contain at least 100 disjoint cases")
    raw = dataset.read_bytes()
    lock = {
        "generated_at": now_iso(), "status": "FROZEN", "frozen": True,
        "dataset_version": FORMAL_VERSION, "sha256": hashlib.sha256(raw).hexdigest(),
        "byte_count": len(raw), "formal_run_count": 0, "result": "NOT_EXECUTED",
    }
    write_json("formal_lock.json", lock, immutable=True)
    print(json.dumps(lock))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
