from concurrent.futures import ThreadPoolExecutor

from app.services.query_embedding_request_cache import QueryEmbeddingRequestCache


def test_request_local_embedding_caches_do_not_cross_contaminate():
    def request(value):
        cache = QueryEmbeddingRequestCache(model="m", dimension=1)
        return cache.get_or_compute("same", lambda: [float(value)])

    with ThreadPoolExecutor(max_workers=2) as executor:
        values = list(executor.map(request, [1, 2]))
    assert values == [[1.0], [2.0]]
