from __future__ import annotations

import json
from collections import Counter

from sqlalchemy import func, select

from task25b_r2_u2_common import RUNTIME, now_iso, write_json

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeChunkVectorIndex, KnowledgeDocument


def main() -> int:
    quality = json.loads((RUNTIME / "huawei_corpus_quality.json").read_text(encoding="utf-8"))
    candidates = [
        item for item in quality.get("records", [])
        if item.get("quality_status") == "READY_FOR_DRAFT_IMPORT"
    ]
    expected_keys = [
        (item.get("file_sha256"), item.get("source_url"))
        for item in candidates
    ]
    with SessionLocal() as db:
        documents = list(db.scalars(select(KnowledgeDocument).where(
            KnowledgeDocument.source_type == "vendor_official"
        )))
        key_counts = Counter(
            ((item.metadata_json or {}).get("file_sha256"), (item.metadata_json or {}).get("source_url"))
            for item in documents
        )
        expected_documents = [item for item in documents if (
            (item.metadata_json or {}).get("file_sha256"),
            (item.metadata_json or {}).get("source_url"),
        ) in set(expected_keys)]
        document_ids = [item.id for item in expected_documents]
        chunk_total = int(db.scalar(select(func.count()).select_from(KnowledgeChunk).where(
            KnowledgeChunk.document_id.in_(document_ids)
        )) or 0) if document_ids else 0
        chunks_without_hash = int(db.scalar(select(func.count()).select_from(KnowledgeChunk).where(
            KnowledgeChunk.document_id.in_(document_ids),
            (KnowledgeChunk.content_hash.is_(None)) | (KnowledgeChunk.content_hash == ""),
        )) or 0) if document_ids else 0
        formal_vector_records = int(db.scalar(
            select(func.count()).select_from(KnowledgeChunkVectorIndex).where(
                KnowledgeChunkVectorIndex.document_id.in_(document_ids)
            )
        ) or 0) if document_ids else 0
    duplicate_keys = [f"{sha}:{url}" for (sha, url), count in key_counts.items() if count > 1]
    pending = sum(item.review_status == "pending_review" for item in expected_documents)
    approved = sum(bool((item.metadata_json or {}).get("approved_for_pilot")) for item in expected_documents)
    parsed_verified = sum(
        item.parse_status == "parsed" and bool((item.metadata_json or {}).get("content_parse_verified"))
        for item in expected_documents
    )
    source_verified = sum(bool((item.metadata_json or {}).get("vendor_source_verified")) for item in expected_documents)
    passed = (
        len(expected_documents) == len(expected_keys)
        and not duplicate_keys
        and pending == len(expected_documents)
        and approved == 0
        and parsed_verified == len(expected_documents)
        and source_verified == len(expected_documents)
        and chunks_without_hash == 0
        and formal_vector_records == 0
    )
    payload = {
        "generated_at": now_iso(),
        "status": "PASSED" if passed else "FAILED",
        "expected_ready_files": len(expected_keys),
        "matching_documents": len(expected_documents),
        "unique_import_keys": len(set(expected_keys)),
        "duplicate_import_keys": duplicate_keys,
        "idempotent_key_policy": "file_sha256+source_url",
        "pending_human_review": pending,
        "vendor_source_verified": source_verified,
        "content_parse_verified": parsed_verified,
        "approved_for_pilot": approved,
        "chunks": chunk_total,
        "chunks_without_content_hash": chunks_without_hash,
        "formal_vector_records": formal_vector_records,
        "automatic_approval": False,
    }
    write_json("huawei_import_integrity.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
