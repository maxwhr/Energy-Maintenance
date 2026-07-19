import httpx
import pytest

from app.services.vector_store_adapters.base import VectorStoreAdapterError
from tests.unit.test_semantic_unit_retry_policy import SequenceClient, response
from tests.unit.task25f_r1_coalescing_helpers import adapter


@pytest.mark.parametrize("status", [400, 401, 403, 404, 500])
def test_non_retryable_http_errors_are_not_retried(monkeypatch, status):
    instance = adapter(timeout_seconds=2)
    client = SequenceClient([response(status, {}), response(200, {"code": 0, "output": []})])
    monkeypatch.setattr(instance, "_shared_client", lambda *_args: client)
    with pytest.raises(VectorStoreAdapterError, match=str(status)):
        instance._request("POST", "/query", payload={})
    assert client.calls == 1


def test_provider_validation_error_is_not_retried(monkeypatch):
    instance = adapter(timeout_seconds=2)
    client = SequenceClient([
        response(200, {"code": -1, "message": "invalid filter"}),
        response(200, {"code": 0, "output": []}),
    ])
    monkeypatch.setattr(instance, "_shared_client", lambda *_args: client)
    with pytest.raises(VectorStoreAdapterError, match="API error code"):
        instance._request("POST", "/query", payload={})
    assert client.calls == 1
