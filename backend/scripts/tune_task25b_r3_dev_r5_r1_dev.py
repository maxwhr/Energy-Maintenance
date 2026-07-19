from __future__ import annotations

from task25b_r3_dev_r5_r1_common import OUT, read_json


def main() -> None:
    rerank = read_json(OUT / "rerank_probe.json")
    canary = read_json(OUT / "canary_result.json")
    if rerank.get("status") != "PASSED":
        raise SystemExit("R5_R1_TUNING_BLOCKED: required real Rerank probe did not pass")
    if canary.get("status") != "PASSED":
        raise SystemExit("R5_R1_TUNING_BLOCKED: immutable Canary did not pass")
    raise SystemExit("R5_R1 tuning requires a new explicitly authorized task")


if __name__ == "__main__":
    main()
