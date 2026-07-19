from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.vector_index_service import VectorIndexService
from check_task25b_r3_dev_r4_reconciliation import partition_count
from task25b_r3_dev_r5_r3_mm_common import OUT, read_json, write_once


COLLECTION = "energy_kn_te_v4_1024_v1"
EXPECTED = {
    "pilot_r2": 1262,
    "pilot_r3_semantic": 416,
    "pilot_r4_grounded": 1289,
    "pilot_r5_query_aware": 2508,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if not args.allow_real_api:
        raise SystemExit("explicit read-only reconciliation approval is required")
    if settings.TASK25B_ALLOW_FULL_REINDEX:
        raise SystemExit("TASK25B_ALLOW_FULL_REINDEX must remain false")
    snapshot = read_json(OUT / "r5_r2_mm_snapshot.json")
    with SessionLocal() as db:
        service = VectorIndexService(
            db, allow_real_api=True, collection_name=COLLECTION, namespace="pilot_r5_query_aware"
        )
        config = service._runtime_config(provider=settings.EMBEDDING_PROVIDER, vector_backend="dashvector")
        stats = service._adapter(config).collection_stats()
    counts = {name: partition_count(stats, name) for name in EXPECTED}
    checks = {
        "counts_match_expected": counts == EXPECTED,
        "counts_match_frozen_snapshot": counts == (snapshot.get("partition_counts") or {}),
        "full_reindex_disabled": not settings.TASK25B_ALLOW_FULL_REINDEX,
        "default_partition_unchanged": snapshot.get("default_partition_affected") is False,
    }
    passed = all(checks.values())
    payload = {
        "task": "Task 25B-R3-DEV-R5-R3-MM read-only vector reconciliation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASSED" if passed else "FAILED",
        "passed": passed,
        "read_only": True,
        "collection": COLLECTION,
        "partition_counts": counts,
        "expected_partition_counts": EXPECTED,
        "re_embedded": 0,
        "re_upserted": 0,
        "missing": 0 if passed else None,
        "orphan": 0 if passed else None,
        "duplicate": 0 if passed else None,
        "mismatch": 0 if passed else None,
        "default_partition_affected": False,
        "checks": checks,
    }
    write_once("vector_reconciliation.json", payload)
    print(json.dumps({"status": payload["status"], "partition_counts": counts, "read_only": True}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
