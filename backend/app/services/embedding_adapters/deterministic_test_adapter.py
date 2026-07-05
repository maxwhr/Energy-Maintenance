from __future__ import annotations

import hashlib
import math
import re

from app.services.embedding_adapters.base import EmbeddingAdapter, EmbeddingResult


class DeterministicTestEmbeddingAdapter(EmbeddingAdapter):
    provider_code = "deterministic_test"

    def __init__(self, *, dimension: int = 384, model: str = "deterministic_hash_v1"):
        self.dimension = max(32, int(dimension or 384))
        self.model = model

    def check_status(self) -> dict:
        return {
            "provider": self.provider_code,
            "model": self.model,
            "dimension": self.dimension,
            "status": "available",
            "test_provider": True,
            "external_api_called": False,
        }

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        vectors = [self._embed(text or "") for text in texts]
        return EmbeddingResult(
            vectors=vectors,
            provider=self.provider_code,
            model=self.model,
            dimension=self.dimension,
            metadata={"test_provider": True, "external_api_called": False},
        )

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = self._tokens(text)
        if not tokens:
            tokens = [hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:12] or "empty"]
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8", errors="ignore"), digest_size=16).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + (len(token) % 7) / 10.0
            vector[index] += sign * weight
        norm = math.sqrt(sum(item * item for item in vector)) or 1.0
        return [round(item / norm, 8) for item in vector]

    @staticmethod
    def _tokens(text: str) -> list[str]:
        normalized = text.lower()
        words = re.findall(r"[a-z0-9_+\-.]{2,}", normalized)
        chinese = re.findall(r"[\u4e00-\u9fff]{2,}", normalized)
        grams: list[str] = []
        for item in chinese:
            for size in (2, 3, 4):
                grams.extend(item[index : index + size] for index in range(max(0, len(item) - size + 1)))
        domain_terms = [
            "逆变器",
            "光伏",
            "华为",
            "阳光电源",
            "告警",
            "绝缘",
            "过温",
            "风扇",
            "通信",
            "离线",
            "排查",
            "检修",
            "sun2000",
            "fusionsolar",
            "sg",
        ]
        grams.extend(term for term in domain_terms if term in normalized)
        return [*words, *grams]
