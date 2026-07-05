from __future__ import annotations

from dataclasses import dataclass, field


class EmbeddingAdapterError(RuntimeError):
    pass


@dataclass
class EmbeddingResult:
    vectors: list[list[float]]
    provider: str
    model: str
    dimension: int
    metadata: dict = field(default_factory=dict)


class EmbeddingAdapter:
    provider_code = "base"

    def check_status(self) -> dict:
        raise NotImplementedError

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        raise NotImplementedError
