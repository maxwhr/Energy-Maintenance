from __future__ import annotations

from task25b_r3_dev_r5_r1_common import FORMAL_VERSION, OUT, read_json


def main() -> None:
    canary = read_json(OUT / "canary_result.json")
    if canary.get("status") != "PASSED" or not canary.get("formal_test_allowed"):
        raise SystemExit(
            "FORMAL_TEST_CREATION_BLOCKED: R5-R1 Canary did not pass; "
            f"{FORMAL_VERSION} was not created"
        )
    raise SystemExit("formal test creation requires a separate explicitly authorized run")


if __name__ == "__main__":
    main()
