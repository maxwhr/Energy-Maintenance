from tests.unit.task25f_r1_coalescing_helpers import adapter, context, payload


def test_coalescing_key_contains_every_safety_dimension():
    instance = adapter()
    components = instance._coalescing_key_components(payload(), request_context=context())
    assert set(components) >= {
        "provider", "endpoint_hash", "collection", "partition", "operation",
        "embedding_provider", "embedding_model", "embedding_dimension", "vector_content_hash",
        "top_k", "filter_expression_hash", "score_threshold", "metadata_output_fields",
        "namespace", "distance_metric", "query_mode", "index_version",
        "retrieval_config_version", "scope_fingerprint",
    }
    assert "vector" not in components


def test_model_dimension_operation_and_scope_change_key():
    instance = adapter()
    base = instance._coalescing_cache_key(payload(), request_context=context())
    variants = [
        context(embedding_model="another-model"),
        context(embedding_dimension=3),
        context(operation="SEMANTIC_UNIT", query_mode="semantic_unit"),
        context(scope_fingerprint="scope-b"),
    ]
    assert all(instance._coalescing_cache_key(payload(), request_context=value) != base for value in variants)
