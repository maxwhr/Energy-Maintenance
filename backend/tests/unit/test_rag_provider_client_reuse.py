from app.services.vector_store_adapters.dashvector_adapter import DashVectorAdapter
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import sleep


def test_dashvector_http_client_is_shared_by_endpoint():
    first = DashVectorAdapter._shared_client("https://example.invalid", 1)
    second = DashVectorAdapter._shared_client("https://example.invalid", 1)
    assert first is second


def test_identical_dashvector_queries_are_coalesced(monkeypatch):
    adapter = DashVectorAdapter(
        endpoint="https://coalescing.example.invalid",
        api_key="test-only",
        collection_name="test_collection",
        namespace="test_partition",
        dimension=2,
        allow_real_api=True,
    )
    calls = 0
    lock = Lock()

    def fake_request(*_args, **_kwargs):
        nonlocal calls
        with lock:
            calls += 1
        sleep(0.03)
        return {"output": [{"id": "v1", "score": 0.1, "fields": {"chunk_id": "c1"}}]}

    monkeypatch.setattr(adapter, "_request", fake_request)
    with adapter._query_cache_lock:
        adapter._query_cache.clear()
        adapter._query_inflight.clear()
        DashVectorAdapter._query_cache_hits = 0
        DashVectorAdapter._query_network_requests = 0
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda _index: adapter.query_vectors(vector=[0.1, 0.2], top_k=5), range(5)))

    assert calls == 1
    assert [[hit.vector_id for hit in result] for result in results] == [["v1"]] * 5
    assert adapter.query_coalescing_snapshot()["network_requests"] == 1
    assert adapter.query_coalescing_snapshot()["cache_hits"] == 4
