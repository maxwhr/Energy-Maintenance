from __future__ import annotations

from app.services.vector_store_adapters.dashvector_adapter import DashVectorAdapter


def adapter(**overrides) -> DashVectorAdapter:
    values = {
        "endpoint": "https://task25f-r1.example.invalid",
        "api_key": "test-only",
        "collection_name": "collection_a",
        "namespace": "partition_a",
        "dimension": 2,
        "metric": "cosine",
        "allow_real_api": True,
        "embedding_provider": "dashscope",
        "embedding_model": "text-embedding-v4",
        "index_version": "index-v1",
        "retrieval_config_version": "retrieval-v1",
    }
    values.update(overrides)
    return DashVectorAdapter(**values)


def payload(*, top_k: int = 10, filter_value: str = "status = 'active'") -> dict:
    return {
        "vector": [0.1, 0.2],
        "topk": top_k,
        "include_vector": False,
        "partition": "partition_a",
        "filter": filter_value,
        "output_fields": ["chunk_id", "document_id"],
    }


def context(**overrides) -> dict:
    value = {
        "operation": "RAW_VECTOR",
        "query_mode": "raw_vector",
        "embedding_provider": "dashscope",
        "embedding_model": "text-embedding-v4",
        "embedding_dimension": 2,
        "score_threshold": 0.2,
        "index_version": "index-v1",
        "retrieval_config_version": "retrieval-v1",
        "scope_fingerprint": "scope-a",
    }
    value.update(overrides)
    return value


def reset_cache() -> None:
    with DashVectorAdapter._query_cache_lock:
        DashVectorAdapter._query_cache.clear()
        DashVectorAdapter._query_inflight.clear()
        DashVectorAdapter._query_cache_hits = 0
        DashVectorAdapter._query_network_requests = 0
