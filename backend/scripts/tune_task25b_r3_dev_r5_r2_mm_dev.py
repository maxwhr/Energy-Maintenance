from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".runtime" / "task25b_r3_dev_r5_r2_mm"


def main() -> int:
    iteration_path = RUNTIME / "canary_iteration_1.json"
    iteration = json.loads(iteration_path.read_text(encoding="utf-8")) if iteration_path.exists() else {}
    allowed = iteration.get("executed") is True and iteration.get("status") == "FAILED"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "NOT_TUNED_CANARY_NOT_EXECUTED" if not allowed else "TUNING_SLOT_AVAILABLE",
        "tuning_performed": False,
        "weights_changed": False,
        "thresholds_changed": False,
        "reason": "Only one post-iteration-1 Train/Dev calibration is allowed; no executed Canary exists.",
    }
    (RUNTIME / "dev_tuning_result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
