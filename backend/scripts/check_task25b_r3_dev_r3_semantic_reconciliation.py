from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeDocument, MaintenanceSemanticAnchor
from app.services.vector_index_service import VectorIndexService
from task25b_r3_dev_r3_common import SEMANTIC_PARTITION, now_iso, write_json


def partition_count(value: object, partition: str) -> int | None:
    if isinstance(value, dict):
        direct = value.get(partition)
        if isinstance(direct, (int, float, str)):
            try: return int(direct)
            except ValueError: pass
        if isinstance(direct, dict):
            for key in ("count", "doc_count", "total_doc_count", "total"):
                if direct.get(key) is not None: return int(direct[key])
        for value_item in value.values():
            found = partition_count(value_item, partition)
            if found is not None: return found
    if isinstance(value, list):
        for value_item in value:
            found = partition_count(value_item, partition)
            if found is not None: return found
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--partition", required=True)
    args = parser.parse_args()
    if not args.allow_real_api or args.partition != SEMANTIC_PARTITION:
        raise SystemExit("explicit semantic A/B reconciliation required")
    settings = get_settings()
    with SessionLocal() as db:
        anchors = list(db.scalars(select(MaintenanceSemanticAnchor).where(
            MaintenanceSemanticAnchor.namespace == SEMANTIC_PARTITION,
            MaintenanceSemanticAnchor.index_status == "active",
        )))
        service = VectorIndexService(db, allow_real_api=True, collection_name=settings.DASHVECTOR_PHYSICAL_COLLECTION, namespace=SEMANTIC_PARTITION)
        config = service._runtime_config(provider=settings.EMBEDDING_PROVIDER, vector_backend="dashvector")
        adapter = service._adapter(config)
        remote = {}
        batches = [[anchor.vector_id for anchor in anchors[offset:offset + 25]] for offset in range(0, len(anchors), 25)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            for result in pool.map(adapter.fetch_documents, batches):
                remote.update(result)
        stats = adapter.collection_stats()
        documents = {document.id: document for document in db.scalars(select(KnowledgeDocument).where(
            KnowledgeDocument.id.in_({anchor.document_id for anchor in anchors})
        ))}
        missing = sum(anchor.vector_id not in remote for anchor in anchors)
        stale = sum(
            (remote.get(anchor.vector_id, {}).get("fields") or {}).get("content_hash") != anchor.anchor_text_hash
            for anchor in anchors if anchor.vector_id in remote
        )
        duplicate = len(anchors) - len({anchor.vector_id for anchor in anchors})
        language = sum((documents.get(anchor.document_id).metadata_json or {}).get("normalized_language") != "zh-CN" for anchor in anchors if documents.get(anchor.document_id))
        status = sum(documents.get(anchor.document_id).review_status != "approved" or documents.get(anchor.document_id).status != "active" for anchor in anchors if documents.get(anchor.document_id))
        current = sum(not anchor.current_version for anchor in anchors)
        remote_count = partition_count(stats, SEMANTIC_PARTITION)
        payload = {
            "generated_at": now_iso(), "collection": config["collection_name"], "partition": SEMANTIC_PARTITION,
            "source_chunks": len({anchor.source_chunk_id for anchor in anchors}), "anchor_vectors": len(anchors),
            "remote_partition_count": remote_count, "missing_anchor": missing,
            "orphan_anchor": max(0, remote_count - len(anchors)) if remote_count is not None else None,
            "duplicate_anchor_id": duplicate, "representation_hash_mismatch": stale,
            "language_leakage": language, "status_leakage": status, "current_version_leakage": current,
            "default_partition_changed": False, "pilot_r2_changed": False,
            "checks": {
                "missing_zero": missing == 0, "orphan_zero": max(0, remote_count - len(anchors)) == 0 if remote_count is not None else False,
                "duplicate_zero": duplicate == 0, "hash_mismatch_zero": stale == 0,
                "language_zero": language == 0, "status_zero": status == 0, "current_zero": current == 0,
            }, "vectors_exported": False,
        }
        payload["passed"] = all(payload["checks"].values())
    write_json("semantic_reconciliation.json", payload)
    print({"status": "PASSED" if payload["passed"] else "FAILED", **{key: payload[key] for key in ("anchor_vectors", "remote_partition_count", "missing_anchor", "orphan_anchor", "representation_hash_mismatch")}})
    if not payload["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
