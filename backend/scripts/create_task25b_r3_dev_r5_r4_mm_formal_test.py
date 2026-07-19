from __future__ import annotations

import json

from task25b_r3_dev_r5_r4_mm_common import FORMAL_VERSION, OUT, read_json


def main() -> int:
    canary = read_json("canary_result.json")
    deterministic_passed = bool((canary.get("deterministic_only") or {}).get("passed"))
    if not deterministic_passed:
        print(json.dumps({
            "status": "NOT_CREATED_DETERMINISTIC_CANARY_FAILED",
            "dataset_version": FORMAL_VERSION,
            "case_count": 0,
            "formal_test_allowed": False,
            "formal_run_count": 0,
        }))
        return 2
    if (OUT / "formal_test_dataset.json").exists():
        raise SystemExit("formal test dataset already exists and is immutable")
    raise SystemExit(
        "FORMAL_TEST_CREATION_REQUIRES_NEW_BLIND_SOURCE_REVIEW: passing Canary is necessary but the formal set "
        "must also be assembled from a disjoint reviewed source before it can be created"
    )


if __name__ == "__main__":
    raise SystemExit(main())
