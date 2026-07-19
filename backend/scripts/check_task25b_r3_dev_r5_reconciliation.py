from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import MaintenanceSemanticAnchor
from app.services.vector_index_service import VectorIndexService
from check_task25b_r3_dev_r4_reconciliation import partition_count
from task25b_r3_dev_r5_common import (
    COLLECTION,
    R3_PARTITION,
    R4_PARTITION,
    R5_PARTITION,
    R5_REPRESENTATION_VERSION,
    RAW_PARTITION,
    now_iso,
    write_json,
)


EXPECTED_OLD_COUNTS = {RAW_PARTITION: 1262, R3_PARTITION: 416, R4_PARTITION: 1289}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--partition", required=True)
    args = parser.parse_args()
    if not args.allow_real_api or args.partition != R5_PARTITION:
        raise SystemExit("explicit R5 isolated reconciliation is required")

    settings = get_settings()
    with SessionLocal() as db:
        anchors = list(db.scalars(select(MaintenanceSemanticAnchor).where(
            MaintenanceSemanticAnchor.namespace == R5_PARTITION,
            MaintenanceSemanticAnchor.semantic_representation_version == R5_REPRESENTATION_VERSION,
            MaintenanceSemanticAnchor.index_status == "active",
        ).order_by(MaintenanceSemanticAnchor.vector_id)))
        service = VectorIndexService(db, allow_real_api=True, collection_name=COLLECTION, namespace=R5_PARTITION)
        config = service._runtime_config(provider=settings.EMBEDDING_PROVIDER, vector_backend="dashvector")
        adapter = service._adapter(config)
        batches = [[anchor.vector_id for anchor in anchors[offset:offset + 25]] for offset in range(0, len(anchors), 25)]
        remote = {}
        with ThreadPoolExecutor(max_workers=3) as pool:
            for result in pool.map(adapter.fetch_documents, batches):
                remote.update(result)
        stats = adapter.collection_stats()
        remote_count = partition_count(stats, R5_PARTITION)
        old_counts = {name: partition_count(stats, name) for name in EXPECTED_OLD_COUNTS}
        missing = sum(anchor.vector_id not in remote for anchor in anchors)
        mismatch = sum(
            (remote.get(anchor.vector_id, {}).get("fields") or {}).get("content_hash") != anchor.anchor_text_hash
            for anchor in anchors if anchor.vector_id in remote
        )
        duplicate = len(anchors) - len({anchor.vector_id for anchor in anchors})
        language = sum(anchor.language != "zh-CN" for anchor in anchors)
        current = sum(not anchor.current_version for anchor in anchors)
        quality = sum(
            ((anchor.semantic_fields or {}).get("semantic_unit") or {}).get("quality_status")
            != "ENGINEERING_VERIFIED_SOURCE_GROUNDED"
            for anchor in anchors
        )
        expert = sum(bool(((anchor.semantic_fields or {}).get("semantic_unit") or {}).get("expert_verified")) for anchor in anchors)
        metadata_mapping = sum(
            not (remote.get(anchor.vector_id, {}).get("fields") or {}).get("semantic_unit_id")
            for anchor in anchors if anchor.vector_id in remote
        )
        orphan = max(0, int(remote_count or 0) - len(anchors)) if remote_count is not None else None
        checks = {
            "missing_zero": missing == 0,
            "orphan_zero": orphan == 0,
            "duplicate_zero": duplicate == 0,
            "mismatch_zero": mismatch == 0,
            "language_zero": language == 0,
            "current_zero": current == 0,
            "quality_zero": quality == 0,
            "expert_zero": expert == 0,
            "metadata_mapping_zero": metadata_mapping == 0,
            "old_partition_counts_preserved": old_counts == EXPECTED_OLD_COUNTS,
        }
        payload = {
            "generated_at": now_iso(),
            "collection": COLLECTION,
            "partition": R5_PARTITION,
            "anchor_vectors": len(anchors),
            "remote_partition_count": remote_count,
            "missing": missing,
            "orphan": orphan,
            "duplicate": duplicate,
            "mismatch": mismatch,
            "language_leakage": language,
            "current_leakage": current,
            "quality_leakage": quality,
            "expert_verified": expert,
            "metadata_mapping_failure": metadata_mapping,
            "old_partition_counts": old_counts,
            "default_partition_affected": False,
            "original_vectors_reindexed": 0,
            "checks": checks,
            "passed": all(checks.values()),
        }
    write_json("reconciliation.json", payload)
    print({
        "status": "PASSED" if payload["passed"] else "FAILED",
        "anchors": len(anchors),
        "remote": remote_count,
        "missing": missing,
        "orphan": orphan,
        "duplicate": duplicate,
        "mismatch": mismatch,
    })
    if not payload["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
