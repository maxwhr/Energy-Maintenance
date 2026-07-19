from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".runtime" / "task25b_r3_dev_r5_r2_mm"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.parse_args()
    canary = json.loads((RUNTIME / "canary_result.json").read_text(encoding="utf-8"))
    payload = {
        "status": "NOT_RUN_CANARY_FAILED_OR_NOT_RUN",
        "run_count": 0,
        "dataset": None,
        "passed": False,
        "blockers": canary.get("blockers") or ["CANARY_NOT_PASSED"],
    }
    (RUNTIME / "formal_quality_gate.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
