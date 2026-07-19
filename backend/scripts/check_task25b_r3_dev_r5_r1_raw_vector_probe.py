from __future__ import annotations

import argparse
import hashlib

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
from app.services.embedding_service import EmbeddingService
from app.services.retrieval_scope_service import RetrievalScopeService
from app.services.vector_index_service import VectorIndexService
from task25b_r3_dev_r5_r1_common import now_iso, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--partition", default="pilot_r2")
    args = parser.parse_args()
    settings = get_settings()
    if not args.allow_real_api or not settings.TASK25B_ALLOW_REAL_API:
        raise SystemExit("real RAW_VECTOR probe requires explicit real API enablement")
    query = "SUN2000 通信异常 RS485 检查"
    embedded = EmbeddingService(allow_real_api=True).embed_texts([query], provider=settings.EMBEDDING_PROVIDER)
    with SessionLocal() as db:
        scope = RetrievalScopeService(db).resolve(CHINESE_ENGINEERING_PILOT_SCOPE_ID, pilot_required=True)
        hits, diagnostics = VectorIndexService(
            db,
            allow_real_api=True,
            collection_name=scope.collection_name,
            namespace=scope.partition_name,
        ).search(
            query,
            top_k=20,
            filters={"device_type": None},
            scope=scope,
            query_vector=embedded.vectors[0],
        )
    raw_hits = int(diagnostics.get("raw_vector_hits") or 0)
    post_hits = int(diagnostics.get("verified_hits") or len(hits))
    passed = bool(
        scope.partition_name == args.partition
        and diagnostics.get("partition_name") == args.partition
        and raw_hits > 0
        and post_hits > 0
        and "device_type" in (diagnostics.get("none_filters_removed") or [])
        and "device_type" not in (diagnostics.get("effective_filters") or {})
        and diagnostics.get("scope_validation_passed")
    )
    payload = {
        "generated_at": now_iso(),
        "status": "PASSED" if passed else "FAILED",
        "query_hash": hashlib.sha256(query.encode("utf-8")).hexdigest(),
        "embedding_generated": True,
        "embedding_dimension": len(embedded.vectors[0]),
        "collection_name": diagnostics.get("collection_name"),
        "partition_name": diagnostics.get("partition_name"),
        "raw_dashvector_hits": raw_hits,
        "post_filter_hits": post_hits,
        "mapped_candidate_count": len(hits),
        "none_filters_removed": diagnostics.get("none_filters_removed") or [],
        "filtered_reason_counts": diagnostics.get("filtered_reason_counts") or {},
        "raw_vector_ids_hash": diagnostics.get("raw_vector_ids_hash"),
        "verified_chunk_ids_hash": diagnostics.get("verified_chunk_ids_hash"),
        "scope_validation_passed": diagnostics.get("scope_validation_passed"),
        "external_call_counts": diagnostics.get("external_call_counts") or {},
    }
    write_json("raw_vector_probe.json", payload)
    print(payload)
    if not passed:
        raise SystemExit("RAW_VECTOR_PROBE_FAILED")


if __name__ == "__main__":
    main()
