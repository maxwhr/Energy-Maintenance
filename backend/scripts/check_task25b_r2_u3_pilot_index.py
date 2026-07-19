from __future__ import annotations

import argparse
import json

from task25b_r2_u3_common import RUNTIME, now_iso, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--resume-pilot-index", action="store_true")
    args = parser.parse_args()
    gate = json.loads((RUNTIME / "u3_resume_gate.json").read_text(encoding="utf-8"))
    allowed = bool(args.allow_real_api and args.resume_pilot_index and gate.get("pilot_index_allowed"))
    payload = {
        "generated_at": now_iso(), "status": "READY_FOR_U2_PARTITION_INDEXER" if allowed else "BLOCKED_HUMAN_REVIEW",
        "collection": "energy_kn_te_v4_1024_v1", "partition": "pilot_r2",
        "execution_contract": "scripts/run_task25b_r2_u2_pilot_index.py",
        "indexed": 0, "default_partition_written": False, "media_collection_written": False,
        "full_reindex_executed": False, "blocked_reason": None if allowed else gate.get("status"),
    }
    write_json("u3_pilot_index_gate.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
