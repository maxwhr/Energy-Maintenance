from __future__ import annotations

import json

from task25b_r3_dev_r5_r6_common import FORMAL_VERSION, OUT


def main() -> int:
    canary_path = OUT / "canary_iteration_2.json"
    if not canary_path.is_file() or not json.loads(canary_path.read_text(encoding="utf-8")).get("passed"):
        print(json.dumps({
            "status": "NOT_CREATED_CANARY_FAILED", "dataset_version": FORMAL_VERSION,
            "created": False, "case_count": 0, "formal_test_allowed": False, "formal_run_count": 0,
        }))
        return 2
    if (OUT / "formal_test_dataset.json").exists():
        raise SystemExit("formal test dataset already exists and is immutable")
    raise SystemExit(
        "FORMAL_TEST_CREATION_REQUIRES_NEW_DISJOINT_REVIEWED_SOURCE: supply at least 100 cases "
        "that do not overlap Train/Dev, Probe, or Canary; automatic label fabrication is forbidden"
    )


if __name__ == "__main__":
    raise SystemExit(main())
