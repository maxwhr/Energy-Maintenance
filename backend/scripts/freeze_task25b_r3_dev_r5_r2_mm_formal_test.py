from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".runtime" / "task25b_r3_dev_r5_r2_mm"


def main() -> int:
    status_path = RUNTIME / "formal_test_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
    payload = {
        **status,
        "frozen": False,
        "freeze_status": "NOT_FROZEN_FORMAL_DATASET_ABSENT",
        "sha256": None,
    }
    status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
