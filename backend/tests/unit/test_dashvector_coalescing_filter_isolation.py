from tests.unit.task25f_r1_coalescing_helpers import adapter, context, payload


def test_same_vector_different_filter_is_isolated():
    instance = adapter()
    assert instance._coalescing_cache_key(
        payload(filter_value="status = 'active'"), request_context=context()
    ) != instance._coalescing_cache_key(
        payload(filter_value="status = 'pending'"), request_context=context()
    )
