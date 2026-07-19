from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".runtime" / "task25b_r3_dev_r5_r2_mm"


def main() -> int:
    canary = json.loads((RUNTIME / "canary_result.json").read_text(encoding="utf-8"))
    if not canary.get("passed"):
        payload = {
            "status": "NOT_CREATED_CANARY_FAILED_OR_NOT_RUN",
            "dataset": None,
            "case_count": 0,
            "formal_test_allowed": False,
        }
        (RUNTIME / "formal_test_status.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False))
        return 1
    raise RuntimeError("formal dataset creation requires a passed Canary")


if __name__ == "__main__":
    raise SystemExit(main())
