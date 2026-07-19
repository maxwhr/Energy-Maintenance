from __future__ import annotations

from task25b_r3_dev_r5_common import OUT, R5_FORMAL_VERSION, read_json


def main() -> None:
    canary = read_json(OUT / "canary_result.json")
    formal = OUT / "formal_test_dataset.json"
    if not canary.get("passed") or not formal.exists():
        raise SystemExit(
            "FORMAL_TEST_FREEZE_BLOCKED: no Canary-approved formal dataset exists; "
            f"{R5_FORMAL_VERSION} was not frozen"
        )
    raise SystemExit("formal test freeze is blocked until an approved dataset creation implementation is enabled")


if __name__ == "__main__":
    main()
