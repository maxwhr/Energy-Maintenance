import asyncio
import logging
import math

import httpx
import pytest

from app.services.embedding_adapters import DashScopeOpenAICompatibleEmbeddingAdapter, EmbeddingAdapterError


def response_payload(count=1, dimension=1024, *, reverse=False, invalid=None):
    items = []
    for index in range(count):
        vector = [float(index + 1)] * dimension
        if invalid is not None:
            vector[0] = invalid
        items.append({"index": index, "embedding": vector})
    if reverse:
        items.reverse()
    return {"data": items, "usage": {"total_tokens": count}}


def adapter(handler, **overrides):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    values = dict(base_url="https://example.invalid/v1", api_key="secret-value", model="text-embedding-v4",
                  dimension=1024, max_retries=1, retry_base_seconds=0.01, allow_real_api=True, client=client)
    values.update(overrides)
    return DashScopeOpenAICompatibleEmbeddingAdapter(**values), client


@pytest.mark.asyncio
async def test_embedding_adapter_response_parse():
    item, client = adapter(lambda request: httpx.Response(200, json=response_payload()))
    try:
        result = await item.aembed_texts(["SUN2000 fault"])
        assert result.dimension == 1024 and len(result.vectors[0]) == 1024
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_embedding_dimension_validation():
    item, client = adapter(lambda request: httpx.Response(200, json=response_payload(dimension=8)))
    try:
        with pytest.raises(EmbeddingAdapterError, match="dimension"):
            await item.aembed_texts(["x"])
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_embedding_batch_limit():
    item, client = adapter(lambda request: httpx.Response(200, json=response_payload(11)))
    try:
        with pytest.raises(EmbeddingAdapterError, match="1 to 10"):
            await item.aembed_texts(["x"] * 11)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_embedding_order_preserved():
    item, client = adapter(lambda request: httpx.Response(200, json=response_payload(2, reverse=True)))
    try:
        result = await item.aembed_texts(["a", "b"])
        assert result.vectors[0][0] == 1 and result.vectors[1][0] == 2
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_embedding_retry_429():
    calls = 0
    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(429) if calls == 1 else httpx.Response(200, json=response_payload())
    item, client = adapter(handler)
    try:
        result = await item.aembed_texts(["retry"])
        assert result.metadata["retries"] == 1 and calls == 2
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_embedding_no_secret_log_and_no_vector_log(caplog):
    item, client = adapter(lambda request: httpx.Response(200, json=response_payload()))
    try:
        with caplog.at_level(logging.INFO):
            await item.aembed_texts(["private input"])
        assert "secret-value" not in caplog.text
        assert "private input" not in caplog.text
        assert str([1.0] * 1024) not in caplog.text
    finally:
        await client.aclose()


def test_embedding_invalid_float_rejected():
    with pytest.raises(EmbeddingAdapterError, match="NaN"):
        DashScopeOpenAICompatibleEmbeddingAdapter._extract_vectors(
            response_payload(invalid=math.nan), expected_count=1, expected_dimension=1024
        )


def test_embedding_content_hash_idempotency():
    from app.services.embedding_service import EmbeddingService
    assert EmbeddingService.content_hash("same") == EmbeddingService.content_hash("same")
