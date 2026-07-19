from __future__ import annotations

import argparse
from collections import Counter

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, MaintenanceSemanticAnchor
from app.services.embedding_service import EmbeddingService
from app.services.vector_store_adapters.base import VectorRecord
from app.services.vector_index_service import VectorIndexService
from task25b_r3_dev_r3_common import SEMANTIC_PARTITION, now_iso, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--partition", required=True)
    parser.add_argument("--max-batches", type=int, default=0)
    args = parser.parse_args()
    if not args.allow_real_api or args.partition != SEMANTIC_PARTITION:
        raise SystemExit("only explicit A/B indexing to pilot_r3_semantic is permitted")
    settings = get_settings()
    with SessionLocal() as db:
        anchors = list(db.scalars(select(MaintenanceSemanticAnchor).where(
            MaintenanceSemanticAnchor.namespace == SEMANTIC_PARTITION,
        ).order_by(MaintenanceSemanticAnchor.source_chunk_id, MaintenanceSemanticAnchor.anchor_type)))
        if not anchors:
            raise SystemExit("semantic representations must be built before indexing")
        service = VectorIndexService(db, allow_real_api=True, collection_name=settings.DASHVECTOR_PHYSICAL_COLLECTION, namespace=SEMANTIC_PARTITION)
        config = service._runtime_config(provider=settings.EMBEDDING_PROVIDER, vector_backend="dashvector")
        if config["embedding_model"] != "text-embedding-v4" or config["embedding_dim"] != 1024:
            raise SystemExit({"invalid_embedding_config": {key: config[key] for key in ("embedding_model", "embedding_dim")}})
        adapter = service._adapter(config)
        adapter.ensure_collection(dimension=1024)
        adapter.ensure_partition(SEMANTIC_PARTITION)
        source_ids = {anchor.source_chunk_id for anchor in anchors}
        chunks = {chunk.id: chunk for chunk in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(source_ids)))}
        document_ids = {anchor.document_id for anchor in anchors}
        documents = {document.id: document for document in db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_(document_ids)))}
        pending = [anchor for anchor in anchors if anchor.index_status != "active" or anchor.index_content_hash != anchor.anchor_text_hash]
        if args.max_batches > 0:
            pending = pending[:args.max_batches * 50]
        embedding = EmbeddingService(allow_real_api=True)
        if embedding.status()["status"] != "available":
            raise SystemExit("real text-embedding-v4 is unavailable")
        indexed = skipped = failed = 0
        for offset in range(0, len(pending), 50):
            batch = pending[offset:offset + 50]
            try:
                embedded = embedding.embed_texts([anchor.anchor_text for anchor in batch], provider=config["embedding_provider"])
                records = []
                for anchor, vector in zip(batch, embedded.vectors):
                    chunk = chunks[anchor.source_chunk_id]
                    document = documents[anchor.document_id]
                    metadata = {
                        "chunk_id": str(anchor.source_chunk_id), "document_id": str(anchor.document_id),
                        "document_title": document.title, "chunk_index": chunk.chunk_index,
                        "manufacturer": document.manufacturer, "product_series": document.product_series,
                        "device_type": document.device_type, "document_type": document.document_type,
                        "review_status": document.review_status, "parse_status": document.parse_status, "status": document.status,
                        "content_hash": anchor.anchor_text_hash, "embedding_model": config["embedding_model"],
                        "embedding_dimension": 1024, "embedding_version": anchor.semantic_representation_version,
                        "device_model": document.model, "fault_codes": ",".join((chunk.metadata_json or {}).get("fault_codes") or []),
                        "section_path": str((chunk.metadata_json or {}).get("heading_path") or chunk.section_title or ""),
                        "page_number": chunk.page_number, "object_type": "semantic_anchor", "vector_backend": "dashvector",
                        "embedding_provider": config["embedding_provider"],
                        "normalized_language": (document.metadata_json or {}).get("normalized_language"),
                        "approval_mode": (document.metadata_json or {}).get("approval_mode"),
                        "approved_for_pilot": bool((document.metadata_json or {}).get("approved_for_pilot")),
                    }
                    records.append(VectorRecord(vector_id=anchor.vector_id, vector=vector, metadata=metadata))
                adapter.upsert_vectors(records)
                for anchor in batch:
                    anchor.index_status = "active"; anchor.index_content_hash = anchor.anchor_text_hash; anchor.error_message = None
                indexed += len(batch)
                db.commit()
            except Exception as exc:  # noqa: BLE001 - record a recoverable per-batch failure without touching raw vectors.
                db.rollback()
                for anchor in batch:
                    db.add(anchor); anchor.index_status = "failed"; anchor.error_message = f"{type(exc).__name__}: {str(exc)[:240]}"
                db.commit()
                failed += len(batch)
        active_count = sum(anchor.index_status == "active" and anchor.index_content_hash == anchor.anchor_text_hash for anchor in anchors)
        remaining = len([anchor for anchor in anchors if anchor.index_status != "active" or anchor.index_content_hash != anchor.anchor_text_hash])
        skipped = len(anchors) - len(pending)
        payload = {
            "generated_at": now_iso(), "collection": config["collection_name"], "partition": SEMANTIC_PARTITION,
            "raw_partition_unchanged": "pilot_r2", "anchor_vectors": len(anchors), "indexed": indexed, "skipped": skipped,
            "failed": failed, "active": active_count, "remaining": remaining,
            "embedding_model": config["embedding_model"], "embedding_dimension": config["embedding_dim"],
            "anchor_types": dict(sorted(Counter(anchor.anchor_type for anchor in anchors).items())),
            "external_embedding_calls_expected": (len(pending) + 9) // 10 if pending else 0,
            "full_reindex": False, "raw_vector_rewrite": False, "expert_verified": False,
        }
    write_json("semantic_anchor_index.json", payload)
    print(payload)
    if failed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
