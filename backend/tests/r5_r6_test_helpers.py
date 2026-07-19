from __future__ import annotations

from app.core.config import Settings
from app.services.rerank_adapters.qwen3_rerank_adapter import Qwen3RerankItem, Qwen3RerankProviderResult


def qwen_settings(**updates) -> Settings:
    values = {
        "DASHSCOPE_API_KEY": "x",
        "DASHSCOPE_RERANK_ENABLED": True,
        "DASHSCOPE_RERANK_MODEL": "qwen3-rerank",
        "DASHSCOPE_RERANK_BASE_URL": "https://workspace.invalid/api/v1",
        "DASHSCOPE_RERANK_ENDPOINT": "/reranks",
        "DASHSCOPE_RERANK_MAX_DOCUMENTS": 40,
        "DASHSCOPE_RERANK_TOP_N": 40,
        "RAG_DEDICATED_RERANK_ENABLED": True,
        "RAG_DEDICATED_RERANK_PROVIDER": "dashscope",
        "RAG_DEDICATED_RERANK_MODEL": "qwen3-rerank",
        "TASK25B_ALLOW_REAL_API": True,
        "TASK25B_ALLOW_FULL_REINDEX": False,
    }
    values.update(updates)
    return Settings(_env_file=None).model_copy(update=values)


class StaticRerankAdapter:
    def __init__(self, indexes: list[int] | None = None, *, status: str = "QWEN3_RERANK_SUCCESS") -> None:
        self.indexes = indexes or []
        self.status = status

    async def rerank(self, **kwargs):
        if self.status != "QWEN3_RERANK_SUCCESS":
            return Qwen3RerankProviderResult(
                success=False,
                status=self.status,
                model="qwen3-rerank",
                fallback_reason=self.status,
            )
        return Qwen3RerankProviderResult(
            success=True,
            status=self.status,
            model="qwen3-rerank",
            results=tuple(
                Qwen3RerankItem(index=index, relevance_score=1.0 - position * 0.1)
                for position, index in enumerate(self.indexes)
            ),
            request_id_hash="0" * 64,
            latency_ms=8.0,
        )
