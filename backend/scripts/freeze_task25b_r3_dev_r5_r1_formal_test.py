from __future__ import annotations

from task25b_r3_dev_r5_r1_common import FORMAL_VERSION, OUT, read_json


def main() -> None:
    canary = read_json(OUT / "canary_result.json")
    formal_manifest = OUT / "formal_test_manifest.json"
    if canary.get("status") != "PASSED" or not formal_manifest.exists():
        raise SystemExit(
            "FORMAL_TEST_FREEZE_BLOCKED: passing Canary and formal manifest are absent; "
            f"{FORMAL_VERSION} remains uncreated"
        )
    raise SystemExit("formal freeze requires a separate explicitly authorized run")


if __name__ == "__main__":
    main()
