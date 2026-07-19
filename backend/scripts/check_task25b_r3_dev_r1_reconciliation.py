from __future__ import annotations

import argparse
import json
import subprocess
import sys

from task25b_r3_dev_common import ROOT, now_iso


OUT = ROOT / ".runtime" / "task25b_r3_dev_r1"


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--partition", required=True); args = parser.parse_args()
    if not args.allow_real_api or args.partition != "pilot_r2":
        raise SystemExit("explicit read-only pilot_r2 reconciliation approval required")
    command = [sys.executable, str(ROOT / "backend" / "scripts" / "check_chinese_pilot_reconciliation.py"),
               "--allow-real-api", "--partition", "pilot_r2"]
    completed = subprocess.run(command, cwd=ROOT / "backend", text=True, capture_output=True, check=False)
    if completed.returncode:
        raise SystemExit(f"read-only reconciliation failed: exit={completed.returncode}")
    source = ROOT / ".runtime" / "task25b_r2_u3_r3_dev" / "chinese_pilot_reconciliation.json"
    result = json.loads(source.read_text(encoding="utf-8"))
    payload = {"generated_at": now_iso(), "read_only": True, "reembedded": 0, "reupserted": 0,
               **result}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pilot_reconciliation.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASSED" if payload.get("passed") else "FAILED", "eligible": payload.get("eligible"),
                      "remote": payload.get("remote_partition_count"), "missing": payload.get("missing"),
                      "orphan": payload.get("orphan"), "reembedded": 0, "reupserted": 0}, ensure_ascii=False))
    if not payload.get("passed"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
