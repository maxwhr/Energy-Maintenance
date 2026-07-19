from __future__ import annotations

import argparse

from task25b_r3_dev_r3_common import OUT, read_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--dataset", default="test_v3_1")
    args = parser.parse_args()
    canary = read_json(OUT / "canary_result.json")
    if not args.allow_real_api or args.dataset != "test_v3_1" or canary.get("status") != "CANARY_PASSED":
        raise SystemExit("formal test_v3_1 quality gate is blocked until Canary passes and a new frozen test set exists")
    raise SystemExit("formal quality gate requires the separately created and frozen test_v3_1 dataset")


if __name__ == "__main__":
    main()
