from __future__ import annotations

import argparse
import json
import time

from sqlalchemy import select

from task25b_r2_u2_common import now_iso, write_json

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeDocument, User
from app.services.vector_index_service import VectorIndexService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--pilot-only", action="store_true")
    parser.add_argument("--approved-only", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if not (args.allow_real_api and args.pilot_only and args.approved_only):
        raise SystemExit("all explicit safety flags are required")
    with SessionLocal() as db:
        documents = list(db.scalars(select(KnowledgeDocument).where(
            KnowledgeDocument.source_type == "vendor_official",
            KnowledgeDocument.review_status == "approved",
            KnowledgeDocument.parse_status == "parsed",
            KnowledgeDocument.status == "active",
        ).order_by(KnowledgeDocument.created_at)))
        eligible = [item for item in documents if bool((item.metadata_json or {}).get("approved_for_pilot"))]
        eligible_chunks = sum(item.chunk_count for item in eligible)
        payload = {
            "generated_at": now_iso(), "status": "BLOCKED_HUMAN_REVIEW" if not eligible else "RUNNING",
            "collection": settings.DASHVECTOR_PHYSICAL_COLLECTION,
            "partition": settings.DASHVECTOR_PILOT_PARTITION,
            "eligible_documents": len(eligible), "eligible_chunks": eligible_chunks,
            "indexed": 0, "skipped": 0, "failed": 0, "duration_seconds": 0.0,
            "pending_indexed": 0, "marketing_indexed": 0, "duplicate_indexed": 0,
            "default_partition_written": False, "media_collection_written": False,
            "full_reindex_executed": False,
        }
        if not eligible:
            write_json("pilot_partition_index_result.json", payload)
            print(json.dumps(payload, ensure_ascii=False))
            return 2
        if not (settings.TASK25B_ALLOW_REAL_API and settings.DASHVECTOR_REAL_CALL_ENABLED and settings.EMBEDDING_REAL_CALL_ENABLED):
            payload.update(status="BLOCKED_CONFIG", blocked_reason="real API gates are disabled")
            write_json("pilot_partition_index_result.json", payload)
            return 2
        admin = db.scalar(select(User).where(User.role == "admin", User.is_active.is_(True)).order_by(User.created_at))
        if not admin:
            payload.update(status="BLOCKED_CONFIG", blocked_reason="active admin audit actor is unavailable")
            write_json("pilot_partition_index_result.json", payload)
            return 2
        started = time.perf_counter()
        service = VectorIndexService(
            db, allow_real_api=True, collection_name=settings.DASHVECTOR_PHYSICAL_COLLECTION,
            namespace=settings.DASHVECTOR_PILOT_PARTITION,
        )
        for document in eligible:
            metadata = document.metadata_json or {}
            if metadata.get("marketing_only") or metadata.get("duplicate") or metadata.get("source_provenance") != "VENDOR_OFFICIAL":
                payload["failed"] += document.chunk_count
                continue
            result = service.index_document(document.id, current_user=admin)
            payload["indexed"] += result.succeeded_count
            payload["skipped"] += result.skipped_count
            payload["failed"] += result.failed_count
        payload["duration_seconds"] = round(time.perf_counter() - started, 3)
        payload["status"] = "PASSED" if payload["failed"] == 0 else "PARTIAL_FAILED"
        write_json("pilot_partition_index_result.json", payload)
        print(json.dumps(payload, ensure_ascii=False))
        return 0 if payload["status"] == "PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
