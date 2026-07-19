from __future__ import annotations

import argparse
from collections import Counter

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, MaintenanceSemanticAnchor
from app.services.embedding_service import EmbeddingService
from app.services.vector_index_service import VectorIndexService
from app.services.vector_store_adapters.base import VectorRecord
from task25b_r3_dev_r4_common import COLLECTION, OUT, R4_PARTITION, now_iso, sha256_text, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--partition", required=True)
    parser.add_argument("--max-batches", type=int, default=0)
    args = parser.parse_args()
    if not args.allow_real_api or args.partition != R4_PARTITION:
        raise SystemExit("only explicit R4 A/B indexing to pilot_r4_grounded is permitted")
    settings = get_settings()
    with SessionLocal() as db:
        anchors = list(db.scalars(select(MaintenanceSemanticAnchor).where(
            MaintenanceSemanticAnchor.namespace == R4_PARTITION,
        ).order_by(MaintenanceSemanticAnchor.source_chunk_id, MaintenanceSemanticAnchor.anchor_type)))
        if not anchors:
            raise SystemExit("R4 semantic units must be materialized first")
        service = VectorIndexService(db, allow_real_api=True, collection_name=COLLECTION, namespace=R4_PARTITION)
        config = service._runtime_config(provider=settings.EMBEDDING_PROVIDER, vector_backend="dashvector")
        if config["collection_name"] != COLLECTION or config["embedding_model"] != "text-embedding-v4" or config["embedding_dim"] != 1024:
            raise SystemExit("R4 real embedding/vector configuration mismatch")
        adapter = service._adapter(config)
        adapter.ensure_collection(dimension=1024)
        adapter.ensure_partition(R4_PARTITION)
        source_ids = {anchor.source_chunk_id for anchor in anchors}
        chunks = {chunk.id: chunk for chunk in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(source_ids)))}
        documents = {document.id: document for document in db.scalars(select(KnowledgeDocument).where(
            KnowledgeDocument.id.in_({anchor.document_id for anchor in anchors})
        ))}
        pending_all = [anchor for anchor in anchors if anchor.index_status != "active" or anchor.index_content_hash != anchor.anchor_text_hash]
        pending = pending_all[:args.max_batches * 50] if args.max_batches > 0 else pending_all
        embedding = EmbeddingService(allow_real_api=True)
        if embedding.status()["status"] != "available":
            raise SystemExit("real text-embedding-v4 is unavailable")
        indexed = failed = 0
        for offset in range(0, len(pending), 50):
            batch = pending[offset:offset + 50]
            try:
                embedded = embedding.embed_texts([anchor.anchor_text for anchor in batch], provider=config["embedding_provider"])
                records = []
                for anchor, vector in zip(batch, embedded.vectors):
                    chunk = chunks[anchor.source_chunk_id]
                    document = documents[anchor.document_id]
                    semantic = (anchor.semantic_fields or {}).get("semantic_unit") or {}
                    source_chunk_ids = semantic.get("source_chunk_ids") or [str(anchor.source_chunk_id)]
                    records.append(VectorRecord(vector_id=anchor.vector_id, vector=vector, metadata={
                        "object_type": "maintenance_semantic_unit", "semantic_unit_id": semantic.get("semantic_unit_id"),
                        "source_chunk_ids_hash": sha256_text("|".join(source_chunk_ids)), "chunk_id": str(anchor.source_chunk_id),
                        "document_id": str(anchor.document_id), "anchor_type": anchor.anchor_type,
                        "representation_version": anchor.semantic_representation_version,
                        "content_hash": anchor.anchor_text_hash, "normalized_language": anchor.language,
                        "approval_mode": anchor.approval_mode, "approved_for_pilot": True,
                        "current_version": anchor.current_version, "quality_status": semantic.get("quality_status"),
                        "manufacturer": document.manufacturer, "product_series": document.product_series,
                        "device_type": document.device_type, "document_type": document.document_type,
                        "review_status": document.review_status, "status": document.status,
                        "section_path": str(anchor.source_locator.get("section_path") or anchor.source_locator.get("section") or ""),
                        "page_number": chunk.page_number, "embedding_model": config["embedding_model"],
                        "embedding_dimension": 1024, "vector_backend": "dashvector",
                    }))
                adapter.upsert_vectors(records)
                for anchor in batch:
                    anchor.index_status = "active"; anchor.index_content_hash = anchor.anchor_text_hash; anchor.error_message = None
                db.commit(); indexed += len(batch)
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                for anchor in batch:
                    db.add(anchor); anchor.index_status = "failed"; anchor.error_message = f"{type(exc).__name__}: {str(exc)[:240]}"
                db.commit(); failed += len(batch)
        active = sum(anchor.index_status == "active" and anchor.index_content_hash == anchor.anchor_text_hash for anchor in anchors)
        remaining = len(anchors) - active
        payload = {
            "generated_at": now_iso(), "collection": config["collection_name"], "partition": R4_PARTITION,
            "raw_partition_unchanged": "pilot_r2", "r3_partition_unchanged": "pilot_r3_semantic",
            "semantic_units": len({((anchor.semantic_fields or {}).get("semantic_unit_id")) for anchor in anchors}),
            "anchor_vectors": len(anchors), "indexed_this_run": indexed, "failed_this_run": failed,
            "active": active, "remaining": remaining, "anchor_types": dict(sorted(Counter(anchor.anchor_type for anchor in anchors).items())),
            "embedding_model": config["embedding_model"], "embedding_dimension": config["embedding_dim"],
            "full_reindex": False, "raw_vector_rewrite": False, "benchmark_query_used": False,
            "expert_verified": False, "external_embedding_calls_expected": (len(pending) + 9) // 10,
        }
    write_json("semantic_unit_index.json", payload)
    print({"status": "INDEXED" if not failed else "FAILED", "indexed": indexed, "active": active, "remaining": remaining, "failed": failed})
    if failed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

