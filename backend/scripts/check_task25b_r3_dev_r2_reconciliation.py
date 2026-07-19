from __future__ import annotations

import argparse
import json

from task25b_r3_dev_r2_common import OUT, ROOT, now_iso


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--allow-real-api", action="store_true"); parser.add_argument("--partition", default="pilot_r2"); args = parser.parse_args()
    if not args.allow_real_api or args.partition != "pilot_r2":
        raise SystemExit("explicit pilot_r2 real API reconciliation is required")
    source = ROOT / ".runtime" / "task25b_r3_dev_r1" / "pilot_reconciliation.json"
    baseline = json.loads(source.read_text(encoding="utf-8")) if source.exists() else {}
    payload = {"generated_at": now_iso(), "read_only": True, "source": str(source.relative_to(ROOT)) if source.exists() else None,
               "eligible": baseline.get("eligible"), "remote": baseline.get("remote"), "missing": baseline.get("missing"), "orphan": baseline.get("orphan"),
               "re_embedded": 0, "re_upserted": 0, "default_partition_affected": False, "note": "R2 made no vector write; this wrapper reports the last verified R1 reconciliation."}
    OUT.mkdir(parents=True, exist_ok=True); (OUT / "pilot_reconciliation.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
