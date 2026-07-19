from __future__ import annotations

import json

from task25b_r3_dev_r5_r3_mm_common import OUT, read_json


def main() -> int:
    status = read_json(OUT / "formal_test_status.json")
    if not status.get("formal_test_allowed"):
        print(json.dumps({"status": "NOT_FROZEN_FORMAL_DATASET_ABSENT", "frozen": False}))
        return 2
    raise RuntimeError("formal freeze requires a created dataset")


if __name__ == "__main__":
    raise SystemExit(main())
