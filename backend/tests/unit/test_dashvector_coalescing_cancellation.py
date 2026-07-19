from concurrent.futures import ThreadPoolExecutor
from threading import Event

from tests.unit.task25f_r1_coalescing_helpers import adapter, reset_cache


def test_cancelled_queued_waiter_does_not_cancel_owner(monkeypatch):
    instance = adapter()
    reset_cache()
    started = Event()
    release = Event()
    calls = 0

    def request(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        started.set()
        release.wait(1)
        return {"output": [{"id": "v1", "score": 0.1, "fields": {"chunk_id": "c1"}}]}

    monkeypatch.setattr(instance, "_request", request)
    with ThreadPoolExecutor(max_workers=1) as pool:
        owner = pool.submit(instance.query_vectors, vector=[0.1, 0.2], top_k=5)
        assert started.wait(1)
        cancelled = pool.submit(instance.query_vectors, vector=[0.1, 0.2], top_k=5)
        assert cancelled.cancel()
        release.set()
        assert [item.vector_id for item in owner.result()] == ["v1"]
    assert [item.vector_id for item in instance.query_vectors(vector=[0.1, 0.2], top_k=5)] == ["v1"]
    assert calls == 1
