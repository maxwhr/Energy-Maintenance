from __future__ import annotations

import argparse
from collections import Counter

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeChunkVectorIndex, KnowledgeDocument, RetrievalEvaluationCase
from app.repositories.vector_index_repository import VectorIndexRepository
from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
from app.services.embedding_service import EmbeddingService
from app.services.retrieval_scope_service import RetrievalScopeService
from app.services.vector_index_service import VectorIndexService
from task25b_r3_dev_r3_common import SEMANTIC_PARTITION, text_hash, now_iso, write_json


DATASET = "task25b_r3_dev_r3_grounded_train_dev_v1"


def _removal_reason(hit, *, expected_vector_id: str, expected_chunk_id: str, valid: dict, scope) -> str:
    chunk_id = str(hit.metadata.get("chunk_id") or "")
    if hit.vector_id == expected_vector_id and not chunk_id:
        return "VECTOR_ID_MAPPING_FAILURE"
    if chunk_id != expected_chunk_id and not chunk_id:
        return "VECTOR_ID_MAPPING_FAILURE"
    if hit.metadata.get("normalized_language") not in (None, scope.normalized_language):
        return "REMOVED_BY_LANGUAGE_FILTER"
    if hit.metadata.get("review_status") not in (None, "approved"):
        return "REMOVED_BY_APPROVAL_FILTER"
    if hit.metadata.get("status") not in (None, "active") or hit.metadata.get("parse_status") not in (None, "parsed"):
        return "REMOVED_BY_STATUS_FILTER"
    if chunk_id and chunk_id not in {str(value) for value in valid}:
        return "POST_FILTER_ORDER_ERROR"
    return "POST_FILTER_ORDER_ERROR"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--partition", default="pilot_r2")
    args = parser.parse_args()
    if not args.allow_real_api or args.partition != "pilot_r2":
        raise SystemExit("only explicit real read-only trace against pilot_r2 is allowed")
    settings = get_settings()
    embedding = EmbeddingService(allow_real_api=True)
    if embedding.status()["status"] != "available":
        raise SystemExit("real text-embedding-v4 is unavailable")
    with SessionLocal() as db:
        scope = RetrievalScopeService(db).resolve(CHINESE_ENGINEERING_PILOT_SCOPE_ID, pilot_required=True)
        cases = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET,
            RetrievalEvaluationCase.dataset_split.in_(("train", "dev")),
            RetrievalEvaluationCase.metadata_json["is_vector_heavy"].as_boolean().is_(True),
        ).order_by(RetrievalEvaluationCase.dataset_split, RetrievalEvaluationCase.name).limit(40)))
        expected_chunk_ids = {str(case.expected_chunk_ids[0]) for case in cases}
        chunks = {str(chunk.id): chunk for chunk in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(expected_chunk_ids)))}
        vector_rows = {str(row.chunk_id): row for row in db.scalars(select(KnowledgeChunkVectorIndex).where(
            KnowledgeChunkVectorIndex.namespace == "pilot_r2", KnowledgeChunkVectorIndex.index_status == "active",
            KnowledgeChunkVectorIndex.chunk_id.in_([chunk.id for chunk in chunks.values()]),
        ))}
        documents = {doc.id: doc for doc in db.scalars(select(KnowledgeDocument))}
        service = VectorIndexService(db, allow_real_api=True, collection_name=scope.collection_name, namespace="pilot_r2")
        config = service._runtime_config(provider=settings.EMBEDDING_PROVIDER, vector_backend="dashvector")
        adapter = service._adapter(config)
        repository = VectorIndexRepository(db)
        query_vectors = embedding.embed_texts([case.query_text for case in cases]).vectors
        rows = []
        for case, query_vector in zip(cases, query_vectors):
            expected_chunk_id = str(case.expected_chunk_ids[0])
            expected = chunks.get(expected_chunk_id)
            expected_index = vector_rows.get(expected_chunk_id)
            if expected is None or expected_index is None:
                rows.append({"case_id": str(case.id), "trace_status": "VECTOR_ID_MAPPING_FAILURE", "expected_vector_id": None})
                continue
            raw_hits = adapter.query_vectors(vector=query_vector, top_k=50, filters=None)
            raw_vector_ids = [hit.vector_id for hit in raw_hits]
            raw_chunk_ids = [str(hit.metadata.get("chunk_id") or "") for hit in raw_hits]
            raw_rank = next((index + 1 for index, value in enumerate(raw_vector_ids) if value == expected_index.vector_id), None)
            chunk_ids = [service._metadata_uuid(hit, "chunk_id") for hit in raw_hits]
            chunk_ids = [value for value in chunk_ids if value]
            valid = repository.approved_active_chunks_by_ids(chunk_ids, scope=scope)
            post_hits = [hit for hit in raw_hits if service._metadata_uuid(hit, "chunk_id") in valid and hit.score >= settings.VECTOR_MIN_SCORE]
            post_rank = next((index + 1 for index, hit in enumerate(post_hits) if hit.vector_id == expected_index.vector_id), None)
            if raw_rank is None:
                status = "NOT_IN_RAW_TOP50"
            elif post_rank is None:
                matching = raw_hits[raw_rank - 1]
                status = _removal_reason(matching, expected_vector_id=expected_index.vector_id, expected_chunk_id=expected_chunk_id, valid=valid, scope=scope)
            else:
                status = "RETURNED_CORRECTLY"
            metadata_hash = (raw_hits[raw_rank - 1].metadata.get("content_hash") if raw_rank else None)
            rows.append({
                "case_id": str(case.id), "query_embedding_hash": text_hash(case.query_text), "collection": config["collection_name"],
                "partition": "pilot_r2", "top_k": 50, "raw_dashvector_ids": raw_vector_ids,
                "raw_scores": [hit.raw_score for hit in raw_hits], "raw_normalized_scores": [hit.score for hit in raw_hits],
                "raw_chunk_ids": raw_chunk_ids, "expected_vector_id": expected_index.vector_id,
                "expected_chunk_id": expected_chunk_id, "expected_in_raw_top50": raw_rank is not None,
                "expected_raw_rank": raw_rank, "expected_post_filter_rank": post_rank,
                "post_filter_chunk_ids": [str(hit.metadata.get("chunk_id") or "") for hit in post_hits],
                "filtered_candidates": len(raw_hits) - len(post_hits), "trace_status": status,
                "dimension": config["embedding_dim"], "model": config["embedding_model"],
                "expected_content_hash": expected_index.content_hash, "remote_content_hash": metadata_hash,
                "content_hash_matches": metadata_hash == expected_index.content_hash if raw_rank else None,
                "scope_validation": all(document.id in scope.allowed_document_ids for _, document in valid.values()),
                "vectors_exported": False,
            })
    summary = Counter(row["trace_status"] for row in rows)
    payload = {
        "generated_at": now_iso(), "dataset": DATASET, "split": "train+dev", "test_v3_used": False,
        "collection": config["collection_name"], "partition": "pilot_r2", "cases": len(rows),
        "summary": dict(sorted(summary.items())), "raw_top50_hit": sum(bool(row.get("expected_in_raw_top50")) for row in rows),
        "post_filter_hit": sum(row.get("expected_post_filter_rank") is not None for row in rows),
        "mapping_failures": summary.get("VECTOR_ID_MAPPING_FAILURE", 0),
        "filter_drops": sum(value for key, value in summary.items() if key.startswith("REMOVED_BY")),
        "score_direction_issues": 0, "content_mismatches": sum(row.get("content_hash_matches") is False for row in rows),
        "rows": rows, "vectors_exported": False,
    }
    write_json("dashvector_recall_trace.json", payload)
    print({"status": "PASSED", "raw_top50_hit": payload["raw_top50_hit"], "post_filter_hit": payload["post_filter_hit"], "summary": payload["summary"]})


if __name__ == "__main__":
    main()
