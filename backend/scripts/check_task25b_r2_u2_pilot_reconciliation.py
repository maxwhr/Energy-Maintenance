from __future__ import annotations

import argparse
import json

from sqlalchemy import func, select

from task25b_r2_u2_common import now_iso, write_json

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeChunkVectorIndex, KnowledgeDocument


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-only", action="store_true")
    parser.add_argument("--approved-only", action="store_true")
    args = parser.parse_args()
    if not (args.pilot_only and args.approved_only):
        raise SystemExit("--pilot-only and --approved-only are required")
    settings = get_settings()
    with SessionLocal() as db:
        approved_docs = int(db.scalar(select(func.count()).select_from(KnowledgeDocument).where(
            KnowledgeDocument.source_type == "vendor_official",
            KnowledgeDocument.review_status == "approved",
            KnowledgeDocument.parse_status == "parsed",
            KnowledgeDocument.status == "active",
            KnowledgeDocument.metadata_json["approved_for_pilot"].as_boolean().is_(True),
        )) or 0)
        pilot_records = int(db.scalar(select(func.count()).select_from(KnowledgeChunkVectorIndex).where(
            KnowledgeChunkVectorIndex.collection_name == settings.DASHVECTOR_PHYSICAL_COLLECTION,
            KnowledgeChunkVectorIndex.namespace == settings.DASHVECTOR_PILOT_PARTITION,
            KnowledgeChunkVectorIndex.index_status == "active",
        )) or 0)
    payload = {
        "generated_at": now_iso(),
        "status": "BLOCKED_HUMAN_REVIEW" if approved_docs == 0 else "READY_FOR_EXTERNAL_RECONCILIATION",
        "collection": settings.DASHVECTOR_PHYSICAL_COLLECTION,
        "partition": settings.DASHVECTOR_PILOT_PARTITION,
        "approved_vendor_documents": approved_docs,
        "postgresql_pilot_index_records": pilot_records,
        "dashvector_vectors": None,
        "external_vector_scan_executed": False,
        "blocked_reason": "No human-approved VENDOR_OFFICIAL document is eligible for Pilot indexing" if approved_docs == 0 else None,
        "default_partition_affected": False,
        "media_collection_affected": False,
        "full_reindex_executed": False,
    }
    write_json("pilot_partition_reconciliation.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 2 if approved_docs == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
