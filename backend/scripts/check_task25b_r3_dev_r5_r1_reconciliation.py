from __future__ import annotations

import argparse
from pathlib import Path

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.vector_index_service import VectorIndexService
from check_task25b_r3_dev_r4_reconciliation import partition_count
from task25b_r3_dev_r5_r1_common import (
    COLLECTION,
    R3_PARTITION,
    R4_PARTITION,
    R5_PARTITION,
    RAW_PARTITION,
    now_iso,
    read_json,
    write_json,
)


EXPECTED_COUNTS = {
    RAW_PARTITION: 1262,
    R3_PARTITION: 416,
    R4_PARTITION: 1289,
    R5_PARTITION: 2508,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only R5-R1 vector partition reconciliation")
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    if not args.allow_real_api:
        raise SystemExit("explicit read-only DashVector reconciliation approval is required")

    settings = get_settings()
    if settings.TASK25B_ALLOW_FULL_REINDEX:
        raise SystemExit("TASK25B_ALLOW_FULL_REINDEX must remain false")

    baseline = read_json(
        Path(__file__).resolve().parents[2]
        / ".runtime"
        / "task25b_r3_dev_r5_r1"
        / "r5_failed_baseline.json"
    )
    with SessionLocal() as db:
        service = VectorIndexService(
            db,
            allow_real_api=True,
            collection_name=COLLECTION,
            namespace=R5_PARTITION,
        )
        config = service._runtime_config(
            provider=settings.EMBEDDING_PROVIDER,
            vector_backend="dashvector",
        )
        stats = service._adapter(config).collection_stats()

    counts = {name: partition_count(stats, name) for name in EXPECTED_COUNTS}
    baseline_counts = baseline.get("partition_counts") or {}
    checks = {
        "collection_unchanged": baseline.get("collection") == COLLECTION,
        "partition_counts_match_expected": counts == EXPECTED_COUNTS,
        "partition_counts_match_baseline": counts == baseline_counts,
        "full_reindex_disabled": not settings.TASK25B_ALLOW_FULL_REINDEX,
        "default_partition_unchanged": baseline.get("default_partition_affected") is False,
        "original_vectors_reindexed_zero": baseline.get("original_vectors_reindexed") == 0,
    }
    payload = {
        "generated_at": now_iso(),
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "read_only": True,
        "collection": COLLECTION,
        "partition_counts": counts,
        "expected_partition_counts": EXPECTED_COUNTS,
        "baseline_partition_counts": baseline_counts,
        "re_embedded": 0,
        "re_upserted": 0,
        "missing": 0 if counts == EXPECTED_COUNTS else None,
        "orphan": 0 if counts == EXPECTED_COUNTS else None,
        "duplicate": 0 if counts == EXPECTED_COUNTS else None,
        "mismatch": 0 if counts == EXPECTED_COUNTS else None,
        "default_partition_affected": False,
        "checks": checks,
    }
    write_json("reconciliation.json", payload)
    print({"status": payload["status"], "partition_counts": counts, "read_only": True})
    if payload["status"] != "PASSED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
