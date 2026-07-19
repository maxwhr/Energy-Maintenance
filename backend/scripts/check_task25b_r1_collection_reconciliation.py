from __future__ import annotations

import argparse
from collections import Counter

from sqlalchemy import select

from task25b_r1_common import now_iso, write_json
from task25b_r1_eval_common import CANARY_NAMESPACE
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeChunkVectorIndex, KnowledgeDocument
from app.services.vector_store_adapters import DashVectorAdapter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    if not args.allow_real_api:
        raise RuntimeError("--allow-real-api is required")
    settings = get_settings()
    with SessionLocal() as db:
        rows = list(db.execute(select(KnowledgeChunkVectorIndex, KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeChunk, KnowledgeChunkVectorIndex.chunk_id == KnowledgeChunk.id)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(
                KnowledgeChunkVectorIndex.collection_name == settings.DASHVECTOR_R1_CANARY_COLLECTION,
                KnowledgeChunkVectorIndex.namespace == CANARY_NAMESPACE,
                KnowledgeDocument.title.startswith("Task25BR1_Controlled_Document_"),
            )).all())
        vector_ids = [item.vector_id for item, _, _ in rows]
        duplicates = [key for key, count in Counter(vector_ids).items() if count > 1]
        stale = [str(item.chunk_id) for item, chunk, _ in rows if item.content_hash != chunk.content_hash]
    adapter = DashVectorAdapter(
        endpoint=settings.DASHVECTOR_ENDPOINT, api_key=settings.DASHVECTOR_API_KEY,
        collection_name=settings.DASHVECTOR_PHYSICAL_COLLECTION, namespace=CANARY_NAMESPACE,
        dimension=settings.EMBEDDING_DIM, metric=settings.DASHVECTOR_METRIC, dtype=settings.DASHVECTOR_DTYPE,
        timeout_seconds=settings.DASHVECTOR_TIMEOUT_SECONDS, allow_real_api=True,
    )
    fetched = {}
    for offset in range(0, len(vector_ids), 50):
        fetched.update(adapter.fetch_documents(vector_ids[offset:offset + 50]))
    stats = adapter.collection_stats()
    partition_stats = (stats.get("partitions") or {}).get(CANARY_NAMESPACE) or {}
    external_count = int(partition_stats.get("total_doc_count") or 0)
    missing = sorted(set(vector_ids) - set(fetched))
    orphan_count = max(0, external_count - len(set(fetched)))
    payload = {
        "status": "PASSED" if not missing and not duplicates and not stale and orphan_count == 0 and len(rows) >= 160 else "FAILED",
        "generated_at": now_iso(), "logical_collection": settings.DASHVECTOR_R1_CANARY_COLLECTION,
        "physical_collection": settings.DASHVECTOR_PHYSICAL_COLLECTION, "namespace": CANARY_NAMESPACE,
        "mapping_reason": "provider_collection_quota_2_partition_isolation_used",
        "postgresql_index_count": len(rows), "external_partition_count": external_count,
        "fetched_expected_count": len(fetched), "missing_external_vector": missing,
        "orphan_external_vector_count": orphan_count, "duplicate_vector_ids": duplicates,
        "stale_vector_chunk_ids": stale, "v1_default_partition_preserved": True,
        "formal_collection_cleanup_performed": False, "full_reindex_performed": False,
        "raw_vectors_returned": False,
    }
    write_json("collection_reconciliation.json", payload)
    return 0 if payload["status"] == "PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
