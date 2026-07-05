from __future__ import annotations

import json
import urllib.error
import urllib.request

from app.services.embedding_adapters.base import EmbeddingAdapter, EmbeddingAdapterError, EmbeddingResult


class OpenAICompatibleEmbeddingAdapter(EmbeddingAdapter):
    provider_code = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        dimension: int,
        embeddings_path: str = "/embeddings",
        timeout_seconds: int = 60,
        allow_real_api: bool = False,
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.model = model or ""
        self.dimension = int(dimension or 0)
        self.embeddings_path = embeddings_path if embeddings_path.startswith("/") else f"/{embeddings_path}"
        self.timeout_seconds = timeout_seconds
        self.allow_real_api = allow_real_api

    def check_status(self) -> dict:
        configured = bool(self.base_url and self.api_key and self.model and self.dimension > 0)
        return {
            "provider": self.provider_code,
            "model": self.model or None,
            "dimension": self.dimension,
            "configured": configured,
            "status": "available" if configured and self.allow_real_api else "blocked",
            "blocked_reason": None if configured and self.allow_real_api else "real embedding API is disabled or not configured",
        }

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        if not self.allow_real_api:
            raise EmbeddingAdapterError("real embedding API is disabled; pass allow_real_api explicitly")
        if not (self.base_url and self.api_key and self.model and self.dimension > 0):
            raise EmbeddingAdapterError("embedding API is not configured")
        payload = json.dumps({"model": self.model, "input": texts}, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{self.embeddings_path}",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise EmbeddingAdapterError(f"embedding API HTTP error: {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise EmbeddingAdapterError(f"embedding API network error: {exc.reason}") from exc
        data = json.loads(body)
        vectors = self._extract_vectors(data)
        if len(vectors) != len(texts):
            raise EmbeddingAdapterError("embedding API returned unexpected vector count")
        for vector in vectors:
            if len(vector) != self.dimension:
                raise EmbeddingAdapterError("embedding dimension mismatch")
        return EmbeddingResult(
            vectors=vectors,
            provider=self.provider_code,
            model=self.model,
            dimension=self.dimension,
            metadata={"external_api_called": True},
        )

    @staticmethod
    def _extract_vectors(data: dict) -> list[list[float]]:
        if isinstance(data.get("data"), list):
            return [[float(value) for value in item.get("embedding", [])] for item in data["data"]]
        if isinstance(data.get("embeddings"), list):
            return [[float(value) for value in item] for item in data["embeddings"]]
        output = data.get("output")
        if isinstance(output, dict) and isinstance(output.get("embeddings"), list):
            return [[float(value) for value in item] for item in output["embeddings"]]
        raise EmbeddingAdapterError("embedding API returned unsupported response structure")
