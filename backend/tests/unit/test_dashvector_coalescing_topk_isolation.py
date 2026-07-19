from tests.unit.task25f_r1_coalescing_helpers import adapter, context, payload


def test_same_vector_different_topk_is_isolated():
    instance = adapter()
    assert instance._coalescing_cache_key(payload(top_k=5), request_context=context()) != instance._coalescing_cache_key(
        payload(top_k=50), request_context=context()
    )
