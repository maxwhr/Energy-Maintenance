from __future__ import annotations

import hashlib

from app.core.config import get_settings
from app.services.embedding_adapters import (
    DeterministicTestEmbeddingAdapter,
    EmbeddingAdapterError,
    EmbeddingResult,
    OpenAICompatibleEmbeddingAdapter,
)


class EmbeddingServiceError(ValueError):
    pass


class EmbeddingService:
    def __init__(self, *, allow_real_api: bool = False):
        self.settings = get_settings()
        self.allow_real_api = allow_real_api

    def status(self) -> dict:
        real_configured = bool(
            self.settings.EMBEDDING_BASE_URL
            and self.settings.EMBEDDING_API_KEY
            and self.settings.EMBEDDING_MODEL
            and self.settings.EMBEDDING_DIM > 0
        )
        blocked_reasons: list[str] = []
        if self.settings.EMBEDDING_ENABLED and not real_configured:
            blocked_reasons.append("EMBEDDING_ENABLED=true but embedding provider config is incomplete")
        if not self.settings.EMBEDDING_ENABLED:
            blocked_reasons.append("EMBEDDING_ENABLED=false; real embedding API is disabled")
        return {
            "embedding_enabled": self.settings.EMBEDDING_ENABLED,
            "embedding_provider": self.settings.EMBEDDING_PROVIDER,
            "embedding_model": self.settings.EMBEDDING_MODEL or None,
            "embedding_dimension": self.settings.EMBEDDING_DIM,
            "embedding_configured": real_configured,
            "deterministic_test_enabled": self.settings.EMBEDDING_TEST_PROVIDER_ENABLED,
            "deterministic_test_dimension": self.settings.EMBEDDING_TEST_DIM,
            "allow_real_api": self.allow_real_api,
            "status": "blocked" if blocked_reasons else "available",
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

    def embed_texts(self, texts: list[str], *, provider: str | None = None) -> EmbeddingResult:
        sanitized = [self._sanitize_text(text) for text in texts]
        if not sanitized:
            raise EmbeddingServiceError("No text provided for embedding")
        try:
            result = self.active_provider(provider).embed_texts(sanitized)
        except EmbeddingAdapterError as exc:
            raise EmbeddingServiceError(str(exc)) from exc
        self._validate_result(result, expected_count=len(sanitized))
        return result

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
        return normalized[:8000]

    @staticmethod
    def _validate_result(result: EmbeddingResult, *, expected_count: int) -> None:
        if len(result.vectors) != expected_count:
            raise EmbeddingServiceError("Embedding vector count mismatch")
        if result.dimension <= 0:
            raise EmbeddingServiceError("Embedding dimension must be positive")
        for vector in result.vectors:
            if len(vector) != result.dimension:
                raise EmbeddingServiceError("Embedding dimension mismatch")
