import pytest

from app.services.vector_store_adapters.base import VectorStoreAdapterError
from tests.unit.task25f_r1_coalescing_helpers import adapter, reset_cache


def test_failed_owner_response_is_not_cached(monkeypatch):
    instance = adapter()
    reset_cache()
    calls = 0

    def request(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise VectorStoreAdapterError("test failure")
        return {"output": []}

    monkeypatch.setattr(instance, "_request", request)
    with pytest.raises(VectorStoreAdapterError):
        instance.query_vectors(vector=[0.1, 0.2], top_k=5)
    assert instance.query_vectors(vector=[0.1, 0.2], top_k=5) == []
    assert calls == 2


def test_partial_response_is_not_cached_and_cached_result_is_not_mutable(monkeypatch):
    instance = adapter()
    reset_cache()
    calls = 0

    def request(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"partial": True, "output": [{"id": "partial", "score": 0.2, "fields": {}}]}
        return {"output": [{"id": "complete", "score": 0.1, "fields": {}}]}

    monkeypatch.setattr(instance, "_request", request)
    assert [item.vector_id for item in instance.query_vectors(vector=[0.1, 0.2], top_k=5)] == ["partial"]
    value = instance.query_vectors(vector=[0.1, 0.2], top_k=5)
    assert [item.vector_id for item in value] == ["complete"]
    value[0].metadata["mutated"] = True
    cached = instance.query_vectors(vector=[0.1, 0.2], top_k=5)
    assert "mutated" not in cached[0].metadata
    assert calls == 2
