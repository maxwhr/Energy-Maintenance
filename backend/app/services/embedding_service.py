from __future__ import annotations

import asyncio
import hashlib
import math
import threading
import time

from app.core.config import get_settings
from app.services.embedding_adapters import (
    DashScopeOpenAICompatibleEmbeddingAdapter,
    DeterministicTestEmbeddingAdapter,
    EmbeddingAdapterError,
    EmbeddingResult,
    OpenAICompatibleEmbeddingAdapter,
)


class EmbeddingServiceError(ValueError):
    pass


class EmbeddingService:
    _query_cache: dict[str, tuple[float, EmbeddingResult]] = {}
    _cache_lock = threading.Lock()

    def __init__(self, *, allow_real_api: bool = False):
        self.settings = get_settings()
        self.allow_real_api = bool(
            allow_real_api
            and self.settings.TASK25B_ALLOW_REAL_API
            and self.settings.EMBEDDING_REAL_CALL_ENABLED
        )

    def status(self) -> dict:
        real_configured = bool(
            self.settings.EMBEDDING_BASE_URL
            and self.settings.EMBEDDING_API_KEY
            and self.settings.EMBEDDING_MODEL == "text-embedding-v4"
            and self.settings.EMBEDDING_DIM == 1024
        )
        blocked_reasons: list[str] = []
        if not self.settings.EMBEDDING_ENABLED:
            blocked_reasons.append("EMBEDDING_ENABLED=false")
        if not real_configured:
            blocked_reasons.append("DashScope text-embedding-v4 configuration is incomplete")
        if not self.allow_real_api:
            blocked_reasons.append("real calls require both Task 25B gates and explicit service approval")
        return {
            "embedding_enabled": self.settings.EMBEDDING_ENABLED,
            "embedding_provider": self.settings.EMBEDDING_PROVIDER,
            "embedding_model": self.settings.EMBEDDING_MODEL or None,
            "embedding_dimension": self.settings.EMBEDDING_DIM,
            "embedding_configured": real_configured,
            "embedding_version": self.settings.EMBEDDING_INDEX_VERSION,
            "deterministic_test_enabled": self.settings.EMBEDDING_TEST_PROVIDER_ENABLED,
            "allow_real_api": self.allow_real_api,
            "status": "available" if real_configured and self.allow_real_api else "blocked",
            "blocked_reasons": blocked_reasons,
        }

    def active_provider(self, provider: str | None = None):
        provider = provider or (
            self.settings.EMBEDDING_PROVIDER
            if self.settings.EMBEDDING_ENABLED and self.allow_real_api
            else "deterministic_test"
        )
        if provider == "deterministic_test":
            if not self.settings.EMBEDDING_TEST_PROVIDER_ENABLED:
                raise EmbeddingServiceError("deterministic test embedding provider is disabled")
            return DeterministicTestEmbeddingAdapter(dimension=self.settings.EMBEDDING_TEST_DIM)
        if provider == "dashscope_openai_compatible":
            return DashScopeOpenAICompatibleEmbeddingAdapter(
                base_url=self.settings.EMBEDDING_BASE_URL,
                api_key=self.settings.EMBEDDING_API_KEY,
                model=self.settings.EMBEDDING_MODEL,
                dimension=self.settings.EMBEDDING_DIM,
                embeddings_path=self.settings.EMBEDDING_EMBEDDINGS_PATH,
                encoding_format=self.settings.EMBEDDING_ENCODING_FORMAT,
                timeout_seconds=self.settings.EMBEDDING_TIMEOUT_SECONDS,
                max_retries=self.settings.EMBEDDING_MAX_RETRIES,
                retry_base_seconds=self.settings.EMBEDDING_RETRY_BASE_SECONDS,
                max_concurrency=self.settings.EMBEDDING_MAX_CONCURRENCY,
                allow_real_api=self.allow_real_api and self.settings.EMBEDDING_ENABLED,
            )
        if provider == "openai_compatible":
            return OpenAICompatibleEmbeddingAdapter(
                base_url=self.settings.EMBEDDING_BASE_URL,
                api_key=self.settings.EMBEDDING_API_KEY,
                model=self.settings.EMBEDDING_MODEL,
                dimension=self.settings.EMBEDDING_DIM,
                embeddings_path=self.settings.EMBEDDING_EMBEDDINGS_PATH,
                timeout_seconds=self.settings.EMBEDDING_TIMEOUT_SECONDS,
                allow_real_api=self.allow_real_api and self.settings.EMBEDDING_ENABLED,
            )
        raise EmbeddingServiceError(f"Unsupported embedding provider: {provider}")

    async def aembed_texts(self, texts: list[str], *, provider: str | None = None) -> EmbeddingResult:
        sanitized = [self._sanitize_text(text) for text in texts]
        if not sanitized:
            raise EmbeddingServiceError("No text provided for embedding")
        batch_size = min(10, max(1, self.settings.EMBEDDING_BATCH_SIZE))
        adapter = self.active_provider(provider)
        vectors: list[list[float]] = []
        batch_metadata: list[dict] = []
        try:
            for offset in range(0, len(sanitized), batch_size):
                result = await adapter.aembed_texts(sanitized[offset : offset + batch_size])
                self._validate_result(result, expected_count=len(sanitized[offset : offset + batch_size]))
                vectors.extend(result.vectors)
                batch_metadata.append(result.metadata)
        except EmbeddingAdapterError as exc:
            raise EmbeddingServiceError(str(exc)) from exc
        return EmbeddingResult(
            vectors=vectors,
            provider=adapter.provider_code,
            model=getattr(adapter, "model", provider or "unknown"),
            dimension=len(vectors[0]),
            metadata={"batches": batch_metadata, "batch_count": len(batch_metadata)},
        )

    def embed_texts(self, texts: list[str], *, provider: str | None = None) -> EmbeddingResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.aembed_texts(texts, provider=provider))
        raise EmbeddingServiceError("sync embedding call cannot run inside an active event loop")

    async def aembed_query(self, text: str, *, provider: str | None = None) -> EmbeddingResult:
        normalized = self._sanitize_text(text)
        selected = provider or self.settings.EMBEDDING_PROVIDER
        key = self.content_hash(f"{selected}:{self.settings.EMBEDDING_MODEL}:{self.settings.EMBEDDING_DIM}:{normalized}")
        now = time.monotonic()
        with self._cache_lock:
            cached = self._query_cache.get(key)
            if cached and cached[0] > now:
                item = cached[1]
                return EmbeddingResult(
                    vectors=item.vectors, provider=item.provider, model=item.model, dimension=item.dimension,
                    metadata={**item.metadata, "cache_hit": True, "cache_key_contains_query": False},
                )
            if cached:
                self._query_cache.pop(key, None)
        result = await self.aembed_texts([normalized], provider=provider)
        result.metadata = {**result.metadata, "cache_hit": False, "cache_key_contains_query": False}
        with self._cache_lock:
            self._query_cache[key] = (now + self.settings.EMBEDDING_QUERY_CACHE_TTL_SECONDS, result)
            if len(self._query_cache) > self.settings.EMBEDDING_QUERY_CACHE_MAX_ENTRIES:
                oldest = min(self._query_cache, key=lambda item: self._query_cache[item][0])
                self._query_cache.pop(oldest, None)
        return result

    def embed_query(self, text: str, *, provider: str | None = None) -> EmbeddingResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.aembed_query(text, provider=provider))
        raise EmbeddingServiceError("sync query embedding call cannot run inside an active event loop")

    def embed_text(self, text: str, *, provider: str | None = None) -> EmbeddingResult:
        return self.embed_texts([text], provider=provider)

    @staticmethod
    def content_hash(text: str) -> str:
        return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def _sanitize_text(text: str) -> str:
        normalized = " ".join((text or "").split())
        if not normalized:
            raise EmbeddingServiceError("Text for embedding must not be empty")
        return normalized[:32000]

    @staticmethod
    def _validate_result(result: EmbeddingResult, *, expected_count: int) -> None:
        if len(result.vectors) != expected_count or result.dimension <= 0:
            raise EmbeddingServiceError("Embedding response count or dimension mismatch")
        for vector in result.vectors:
            if len(vector) != result.dimension or not all(math.isfinite(value) for value in vector):
                raise EmbeddingServiceError("Embedding vector dimension or numeric value is invalid")
