from __future__ import annotations

from task25b_r3_dev_r5_r1_common import FORMAL_VERSION, OUT, read_json


def main() -> None:
    canary = read_json(OUT / "canary_result.json")
    freeze = OUT / "formal_test_freeze.json"
    if canary.get("status") != "PASSED" or not freeze.exists():
        raise SystemExit(
            "FORMAL_QUALITY_GATE_BLOCKED: Canary is not passing and no frozen formal set exists; "
            f"{FORMAL_VERSION} run count remains zero"
        )
    raise SystemExit("formal quality gate requires a separate explicitly authorized run")


if __name__ == "__main__":
    main()
