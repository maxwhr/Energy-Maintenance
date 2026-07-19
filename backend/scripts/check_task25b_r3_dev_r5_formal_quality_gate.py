from __future__ import annotations

from task25b_r3_dev_r5_common import OUT, R5_FORMAL_VERSION, read_json


def main() -> None:
    canary = read_json(OUT / "canary_result.json")
    frozen = OUT / "formal_test_freeze.json"
    if not canary.get("passed") or not frozen.exists():
        raise SystemExit(
            "FORMAL_BLIND_TEST_BLOCKED: R5 Canary failed or formal data is not frozen; "
            f"{R5_FORMAL_VERSION} run count remains zero"
        )
    raise SystemExit("formal blind run is blocked until an immutable frozen formal dataset exists")


if __name__ == "__main__":
    main()
