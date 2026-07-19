import httpx

from tests.unit.task25f_r1_coalescing_helpers import adapter


class SequenceClient:
    def __init__(self, values):
        self.values = list(values)
        self.calls = 0

    def request(self, *_args, **_kwargs):
        self.calls += 1
        value = self.values.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value


def response(status: int, body: dict) -> httpx.Response:
    return httpx.Response(
        status,
        json=body,
        request=httpx.Request("POST", "https://task25f-r1.example.invalid/query"),
    )


def test_transient_connect_error_is_retried_once(monkeypatch):
    instance = adapter(timeout_seconds=2)
    client = SequenceClient([
        httpx.ConnectError("reset", request=httpx.Request("POST", instance.endpoint)),
        response(200, {"code": 0, "output": []}),
    ])
    monkeypatch.setattr(instance, "_shared_client", lambda *_args: client)
    assert instance._request("POST", "/query", payload={}) == {"code": 0, "output": []}
    assert client.calls == 2
    assert instance.last_retries == 1


def test_429_and_503_are_retryable_at_most_once(monkeypatch):
    for status in (429, 503):
        instance = adapter(timeout_seconds=2)
        client = SequenceClient([response(status, {}), response(200, {"code": 0, "output": []})])
        monkeypatch.setattr(instance, "_shared_client", lambda *_args, client=client: client)
        assert instance._request("POST", "/query", payload={})["code"] == 0
        assert client.calls == 2
        assert instance.last_retries == 1
