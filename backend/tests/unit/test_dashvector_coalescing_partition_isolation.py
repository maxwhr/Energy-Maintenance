from tests.unit.task25f_r1_coalescing_helpers import adapter, context, payload


def test_same_vector_different_partition_is_isolated():
    first = adapter(namespace="partition_a")
    second = adapter(namespace="partition_b")
    first_payload = payload()
    second_payload = {**payload(), "partition": "partition_b"}
    assert first._coalescing_cache_key(first_payload, request_context=context()) != second._coalescing_cache_key(
        second_payload, request_context=context()
    )
