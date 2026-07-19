from __future__ import annotations

from task25b_r3_dev_r5_common import OUT, R5_FORMAL_VERSION, read_json


def main() -> None:
    canary = read_json(OUT / "canary_result.json")
    if not canary.get("passed"):
        raise SystemExit(
            "FORMAL_TEST_CREATION_BLOCKED: both R5 Canary iterations did not pass; "
            f"{R5_FORMAL_VERSION} was not created"
        )
    raise SystemExit("formal test creation is intentionally unavailable until a passing immutable Canary exists")


if __name__ == "__main__":
    main()
