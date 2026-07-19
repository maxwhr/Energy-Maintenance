from tests.unit.task25f_r1_coalescing_helpers import adapter, context


def test_same_query_different_scope_and_channel_never_share_key():
    instance = adapter()
    payload = {
        "vector": [0.1, 0.2], "topk": 10, "partition": "partition_a",
        "filter": "status = 'active'", "output_fields": ["chunk_id"],
    }
    scope_a = instance._coalescing_cache_key(payload, request_context=context(scope_fingerprint="user-a"))
    scope_b = instance._coalescing_cache_key(payload, request_context=context(scope_fingerprint="user-b"))
    semantic = instance._coalescing_cache_key(
        payload,
        request_context=context(
            scope_fingerprint="user-a", operation="SEMANTIC_UNIT", query_mode="semantic_unit"
        ),
    )
    assert len({scope_a, scope_b, semantic}) == 3
