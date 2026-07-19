from __future__ import annotations

import argparse
import json

from task25b_r2_u3_common import RUNTIME, now_iso, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    index_gate = json.loads((RUNTIME / "u3_pilot_index_gate.json").read_text(encoding="utf-8")) if (RUNTIME / "u3_pilot_index_gate.json").exists() else {}
    payload = {
        "generated_at": now_iso(), "status": "BLOCKED_NO_PILOT_INDEX",
        "collection": "energy_kn_te_v4_1024_v1", "partition": "pilot_r2",
        "external_api_called": False, "postgresql_vectors": 0, "dashvector_vectors": None,
        "missing": None, "orphan": None, "stale": None, "duplicate": None,
        "pending_leakage": 0, "archived_leakage": 0, "marketing_leakage": 0,
        "blocked_reason": index_gate.get("status") or "pilot index not executed",
    }
    write_json("u3_pilot_reconciliation.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
