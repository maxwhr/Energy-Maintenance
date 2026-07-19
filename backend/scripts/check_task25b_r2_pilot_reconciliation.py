from __future__ import annotations

import argparse
import json
from collections import Counter
from uuid import UUID

from sqlalchemy import select

from task25b_r2_common import RUNTIME, now_iso, write_json

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeChunkVectorIndex, KnowledgeDocument
from app.services.vector_store_adapters import DashVectorAdapter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    selection = json.loads((RUNTIME / "pilot_document_selection.json").read_text(encoding="utf-8"))
    collection = json.loads((RUNTIME / "pilot_collection_check.json").read_text(encoding="utf-8"))
    selected_ids = {str(item["document_id"]) for item in selection.get("selected_documents") or []}
    payload = {
        "generated_at": now_iso(), "status": "BLOCKED", "pilot_collection": settings.DASHVECTOR_PILOT_COLLECTION,
        "selected_documents": len(selected_ids), "eligible_chunks": 0, "postgresql_records": 0,
        "dashvector_vectors": None, "missing": None, "orphan": None, "stale": None,
        "duplicate": None, "dimension_mismatch": None, "model_mismatch": None,
        "content_hash_mismatch": None, "leakage": None, "external_api_called": False,
    }
    if not args.allow_real_api or collection.get("status") != "PASSED" or selection.get("status") != "READY":
        payload["blocked_reasons"] = [
            reason for reason in (
                None if args.allow_real_api else "allow_real_api_missing",
                None if collection.get("status") == "PASSED" else collection.get("status"),
                None if selection.get("status") == "READY" else selection.get("status"),
            ) if reason
        ]
        write_json("pilot_reconciliation.json", payload)
        print(json.dumps(payload, ensure_ascii=False))
        return 2

    with SessionLocal() as db:
        chunks = list(db.scalars(select(KnowledgeChunk).join(KnowledgeDocument).where(
            KnowledgeDocument.id.in_([UUID(item) for item in selected_ids]),
            KnowledgeDocument.review_status == "approved", KnowledgeDocument.parse_status == "parsed",
            KnowledgeDocument.status == "active", KnowledgeChunk.status == "active",
        )))
        indexes = list(db.scalars(select(KnowledgeChunkVectorIndex).where(
            KnowledgeChunkVectorIndex.collection_name == settings.DASHVECTOR_PILOT_COLLECTION,
            KnowledgeChunkVectorIndex.namespace == "default",
        )))
        payload["eligible_chunks"] = len(chunks)
        payload["postgresql_records"] = len(indexes)
        expected = {str(item.chunk_id): item for item in indexes}
        duplicate_counts = Counter(item.vector_id for item in indexes)
        payload["duplicate"] = sum(value - 1 for value in duplicate_counts.values() if value > 1)
        payload["stale"] = sum(item.index_status != "active" for item in indexes)
        payload["dimension_mismatch"] = sum(item.embedding_dim != 1024 for item in indexes)
        payload["model_mismatch"] = sum(item.embedding_model != settings.EMBEDDING_MODEL for item in indexes)
        current_hash = {str(item.id): str(item.content_hash or "") for item in chunks}
        payload["content_hash_mismatch"] = sum(current_hash.get(str(item.chunk_id)) != item.content_hash for item in indexes)
        adapter = DashVectorAdapter(
            endpoint=settings.DASHVECTOR_ENDPOINT, api_key=settings.DASHVECTOR_API_KEY,
            collection_name=settings.DASHVECTOR_PILOT_COLLECTION, namespace="default", dimension=1024,
            metric="cosine", dtype="float", timeout_seconds=settings.DASHVECTOR_TIMEOUT_SECONDS,
            allow_real_api=True,
        )
        payload["external_api_called"] = True
        fetched = adapter.fetch_documents([item.vector_id for item in indexes])
        payload["dashvector_vectors"] = len(fetched)
        payload["missing"] = len(indexes) - len(fetched)
        payload["orphan"] = max(0, int(adapter.collection_stats().get("total_doc_count") or len(fetched)) - len(indexes))
        payload["leakage"] = sum(
            str((item.get("fields") or {}).get("document_id")) not in selected_ids for item in fetched.values()
        )
    zero_fields = ["missing", "orphan", "stale", "duplicate", "dimension_mismatch", "model_mismatch", "content_hash_mismatch", "leakage"]
    payload["status"] = "PASSED" if all(payload[name] == 0 for name in zero_fields) else "FAILED"
    write_json("pilot_reconciliation.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] == "PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
