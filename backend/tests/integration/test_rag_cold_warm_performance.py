from app.services.query_embedding_request_cache import QueryEmbeddingRequestCache


def test_warm_request_cache_avoids_second_computation():
    calls = []
    cache = QueryEmbeddingRequestCache(model="m", dimension=1)
    cache.get_or_compute("query", lambda: calls.append("cold") or [1.0])
    cache.get_or_compute("query", lambda: calls.append("warm") or [2.0])
    assert calls == ["cold"]
