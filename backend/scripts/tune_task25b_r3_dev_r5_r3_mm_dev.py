from __future__ import annotations

import json

from task25b_r3_dev_r5_r3_mm_common import OUT, read_json, write_once


def main() -> int:
    canary = read_json(OUT / "canary_result.json")
    if int(canary.get("executed_cases") or 0) == 0:
        payload = {
            "status": "NOT_TUNED_CANARY_NOT_EXECUTED",
            "weights_changed": False,
            "thresholds_changed": False,
            "formal_data_used": False,
        }
        write_once("dev_tuning_result.json", payload)
        print(json.dumps(payload))
        return 2
    raise RuntimeError("tuning requires an executed first Canary iteration")


if __name__ == "__main__":
    raise SystemExit(main())
