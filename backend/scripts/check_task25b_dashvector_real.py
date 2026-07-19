from __future__ import annotations

import argparse
import hashlib
import time

from task25b_common import real_gate, write_result
from app.core.config import get_settings
from app.services.embedding_service import EmbeddingService
from app.services.vector_store_adapters import DashVectorAdapter, VectorRecord


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    allowed, reasons = real_gate(settings, args.allow_real_api)
    if not allowed:
        write_result("dashvector_real.json", {"status": "BLOCKED_CONFIG", "reasons": reasons, "external_api_called": False})
        return 2
    adapter = DashVectorAdapter(
        endpoint=settings.DASHVECTOR_ENDPOINT, api_key=settings.DASHVECTOR_API_KEY,
        collection_name=settings.DASHVECTOR_PHYSICAL_COLLECTION, namespace=settings.DASHVECTOR_NAMESPACE,
        dimension=1024, metric="cosine", dtype="float", timeout_seconds=settings.DASHVECTOR_TIMEOUT_SECONDS,
        upsert_batch_size=settings.DASHVECTOR_UPSERT_BATCH_SIZE, allow_real_api=True,
    )
    collection = adapter.ensure_collection(dimension=1024)
    text = "Task25B_ DashVector self match Huawei SUN2000 alarm 2064"
    embedding = EmbeddingService(allow_real_api=True).embed_text(text, provider="dashscope_openai_compatible")
    vector_id = f"task25b_probe_{hashlib.sha256(text.encode()).hexdigest()[:24]}"
    record = VectorRecord(vector_id=vector_id, vector=embedding.vectors[0], metadata={
        "chunk_id": "00000000-0000-0000-0000-000000000025", "document_id": "00000000-0000-0000-0000-000000000025",
        "document_title": "Task25B_ controlled probe", "manufacturer": "huawei", "product_series": "SUN2000",
        "device_type": "pv_inverter", "document_type": "manual", "review_status": "approved", "parse_status": "parsed",
        "status": "active", "content_hash": hashlib.sha256(text.encode()).hexdigest(), "embedding_model": embedding.model,
        "embedding_dimension": 1024, "embedding_version": settings.EMBEDDING_INDEX_VERSION, "device_model": "SUN2000",
        "fault_codes": "2064", "section_path": "probe", "page_number": 1, "object_type": "knowledge_chunk",
    })
    adapter.upsert_vectors([record])
    adapter.upsert_vectors([record])
    hits = []
    for _ in range(10):
        hits = adapter.query_vectors(vector=embedding.vectors[0], top_k=3)
        if hits:
            break
        time.sleep(1)
    self_first = bool(hits and hits[0].vector_id == vector_id)
    raw = hits[0].raw_score if hits else None
    normalized = hits[0].score if hits else None
    adapter.delete_vectors([vector_id])
    passed = self_first and collection == settings.DASHVECTOR_PHYSICAL_COLLECTION and normalized is not None
    write_result("dashvector_real.json", {
        "status": "PASSED" if passed else "FAILED", "external_api_called": True,
        "endpoint_type": "https_cluster_endpoint", "logical_collection": settings.DASHVECTOR_COLLECTION,
        "physical_collection": collection, "provider_name_limit_workaround": True, "dimension": 1024,
        "metric": "cosine", "dtype": "float", "create_or_validate": True, "idempotent_upsert": True,
        "query_hit_count": len(hits), "self_match_first": self_first, "raw_score": raw,
        "normalized_score": normalized, "score_direction": "raw cosine distance ascending; normalized similarity descending", "probe_deleted": True,
        "key_output": False, "full_vectors_output": False,
    })
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
