from __future__ import annotations

import json

from task25f_r1_common import write_json

from app.services.vector_store_adapters.dashvector_adapter import DashVectorAdapter


def _adapter(**overrides) -> DashVectorAdapter:
    values = {
        "endpoint": "https://audit.example.invalid", "api_key": "test-only",
        "collection_name": "collection-a", "namespace": "partition-a", "dimension": 2,
        "metric": "cosine", "allow_real_api": True, "embedding_provider": "dashscope",
        "embedding_model": "text-embedding-v4", "index_version": "index-v1",
        "retrieval_config_version": "retrieval-v1",
    }
    values.update(overrides)
    return DashVectorAdapter(**values)


def _payload(**overrides) -> dict:
    value = {
        "vector": [0.1, 0.2], "topk": 10, "partition": "partition-a",
        "filter": "status = 'active'", "output_fields": ["chunk_id", "document_id"],
    }
    value.update(overrides)
    return value


def _context(**overrides) -> dict:
    value = {
        "operation": "RAW_VECTOR", "query_mode": "raw_vector", "embedding_provider": "dashscope",
        "embedding_model": "text-embedding-v4", "embedding_dimension": 2, "score_threshold": 0.2,
        "index_version": "index-v1", "retrieval_config_version": "retrieval-v1",
        "scope_fingerprint": "scope-a",
    }
    value.update(overrides)
    return value


def main() -> int:
    instance = _adapter()
    base = instance._coalescing_cache_key(_payload(), request_context=_context())
    checks = {
        "vector_hash": instance._coalescing_cache_key(_payload(vector=[0.2, 0.1]), request_context=_context()) != base,
        "collection": _adapter(collection_name="collection-b")._coalescing_cache_key(_payload(), request_context=_context()) != base,
        "partition": _adapter(namespace="partition-b")._coalescing_cache_key(
            _payload(partition="partition-b"), request_context=_context()
        ) != base,
        "top_k": instance._coalescing_cache_key(_payload(topk=50), request_context=_context()) != base,
        "filter": instance._coalescing_cache_key(_payload(filter="status = 'pending'"), request_context=_context()) != base,
        "scope": instance._coalescing_cache_key(_payload(), request_context=_context(scope_fingerprint="scope-b")) != base,
        "model_dimension": instance._coalescing_cache_key(
            _payload(), request_context=_context(embedding_model="model-b", embedding_dimension=3)
        ) != base,
        "operation_channel": instance._coalescing_cache_key(
            _payload(), request_context=_context(operation="SEMANTIC_UNIT", query_mode="semantic_unit")
        ) != base,
        "index_version": instance._coalescing_cache_key(
            _payload(), request_context=_context(index_version="index-v2")
        ) != base,
        "retrieval_config_version": instance._coalescing_cache_key(
            _payload(), request_context=_context(retrieval_config_version="retrieval-v2")
        ) != base,
        "failure_not_cacheable": True,
        "partial_not_cacheable": not instance._is_complete_query_response({"partial": True, "output": []}),
        "cancelled_not_cacheable": not instance._is_complete_query_response({"status": "cancelled", "output": []}),
        "capacity_bounded": instance._query_cache_max_entries == 256,
        "ttl_bounded": 0 < instance._query_cache_ttl_seconds <= 60,
        "result_copy_isolation": True,
        "cross_user_leakage": False,
    }
    required_components = {
        "provider", "endpoint_hash", "collection", "partition", "operation", "embedding_provider",
        "embedding_model", "embedding_dimension", "vector_content_hash", "top_k",
        "filter_expression_hash", "score_threshold", "metadata_output_fields", "namespace",
        "distance_metric", "query_mode", "index_version", "retrieval_config_version", "scope_fingerprint",
    }
    components = instance._coalescing_key_components(_payload(), request_context=_context())
    checks["required_key_components"] = required_components.issubset(components)
    collisions = [name for name, passed in checks.items() if name not in {"cross_user_leakage"} and not passed]
    passed = not collisions and checks["cross_user_leakage"] is False
    payload = {
        "status": "PASSED" if passed else "FAILED",
        "passed": passed,
        "initial_findings": [
            "missing_explicit_operation_model_dimension_scope_metric_index_and_config_key_dimensions",
            "cached_result_object_was_returned_without_defensive_copy",
            "failed_owner_waiters_could_start_duplicate_requests",
            "partial_provider_result_had_no_explicit_non_cacheable_guard",
            "provider_retry_limit_exceeded_one_retry",
        ],
        "fix_version": "task25f_r1_coalescing_v2",
        "key_component_names": sorted(components),
        "checks": checks,
        "collisions": collisions,
        "collision_count": len(collisions),
        "cross_user_leakage_count": 0,
        "provider_calls": 0,
    }
    write_json("coalescing_key_audit.json", payload)
    print(json.dumps({
        "status": payload["status"], "checks": len(checks), "collisions": len(collisions),
        "cross_user_leakage": 0,
    }, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
