from __future__ import annotations

from task25b_r3_dev_r3_common import OUT, read_json


def main() -> None:
    canary = read_json(OUT / "canary_result.json")
    if canary.get("status") != "CANARY_PASSED":
        raise SystemExit("test_v3_1 freeze is blocked: train/dev semantic Canary did not pass")
    raise SystemExit("test_v3_1 freeze requires a newly generated dataset and human authorization")


if __name__ == "__main__":
    main()
