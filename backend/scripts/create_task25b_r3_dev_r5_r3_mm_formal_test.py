from __future__ import annotations

import json

from task25b_r3_dev_r5_r3_mm_common import OUT, read_json, write_once


def main() -> int:
    canary = read_json(OUT / "canary_result.json")
    if not canary.get("passed"):
        payload = {
            "status": "NOT_CREATED_CONTRACT_OR_CANARY_NOT_PASSED",
            "dataset": None,
            "case_count": 0,
            "formal_test_allowed": False,
            "frozen": False,
        }
        write_once("formal_test_status.json", payload)
        print(json.dumps(payload))
        return 2
    raise RuntimeError("formal dataset creation requires a reviewed passing Canary")


if __name__ == "__main__":
    raise SystemExit(main())
