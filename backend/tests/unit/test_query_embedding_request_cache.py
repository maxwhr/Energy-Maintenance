from app.services.query_embedding_request_cache import QueryEmbeddingRequestCache


def test_request_cache_reuses_only_same_model_dimension_and_query():
    calls = 0
    cache = QueryEmbeddingRequestCache(model="m", dimension=3)

    def compute():
        nonlocal calls
        calls += 1
        return [1.0, 2.0, 3.0]

    assert cache.get_or_compute(" A  B ", compute) == [1.0, 2.0, 3.0]
    assert cache.get_or_compute("a b", compute) == [1.0, 2.0, 3.0]
    assert calls == 1
    assert cache.hits == 1
