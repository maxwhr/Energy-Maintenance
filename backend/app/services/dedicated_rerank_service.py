from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, replace
from typing import Any

from app.core.config import Settings, get_settings
from app.schemas.query_understanding import QueryUnderstandingResult
from app.services.rerank_adapters.qwen3_rerank_adapter import Qwen3RerankAdapter
from app.services.rerank_document_builder import RerankDocumentBuilder
from app.services.rerank_query_builder import RerankQueryBuilder
from app.services.rrf_fusion_service import QueryAwareCandidate


@dataclass(frozen=True, slots=True)
class DedicatedRerankResult:
    candidates: list[QueryAwareCandidate]
    diagnostics: dict[str, Any]


class DedicatedRerankService:
    INSTRUCT_VERSION = "task25b_r3_dev_r5_r6_instruct_v1"
    INSTRUCT = (
        "Given an equipment maintenance troubleshooting query, rank passages that directly answer the user's "
        "requested information. Prefer specific, source-grounded causes, actions, procedures, prerequisites, "
        "safety requirements, and verification steps over generic background or merely topically related text. "
        "Penalize passages with mismatched device models, alarm codes, components, or occurrence conditions."
    )

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        adapter: Qwen3RerankAdapter | None = None,
        document_builder: RerankDocumentBuilder | None = None,
        query_builder: RerankQueryBuilder | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.adapter = adapter or Qwen3RerankAdapter(self.settings)
        self.document_builder = document_builder or RerankDocumentBuilder()
        self.query_builder = query_builder or RerankQueryBuilder()

    def rerank(
        self,
        candidates: list[QueryAwareCandidate],
        *,
        understanding: QueryUnderstandingResult,
        allow_real_api: bool,
        fallback_candidates: list[QueryAwareCandidate] | None = None,
    ) -> DedicatedRerankResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.rerank_async(
                candidates,
                understanding=understanding,
                allow_real_api=allow_real_api,
                fallback_candidates=fallback_candidates,
            ))
        fallback = list(fallback_candidates or candidates)
        return DedicatedRerankResult(
            fallback,
            self._fallback_diagnostics(
                candidates, fallback, "QWEN3_RERANK_ASYNC_CONTEXT_UNSUPPORTED", understanding
            ),
        )

    async def rerank_async(
        self,
        candidates: list[QueryAwareCandidate],
        *,
        understanding: QueryUnderstandingResult,
        allow_real_api: bool,
        fallback_candidates: list[QueryAwareCandidate] | None = None,
    ) -> DedicatedRerankResult:
        original = list(candidates)
        fallback = list(fallback_candidates or original)
        if not original:
            return DedicatedRerankResult([], self._fallback_diagnostics(original, fallback, "EMPTY_CANDIDATES", understanding))
        documents = [self.document_builder.build(item, understanding=understanding) for item in original]
        query = self.query_builder.build(understanding)
        provider = await self.adapter.rerank(
            query=query.text,
            documents=[item.text for item in documents],
            top_n=min(self.settings.DASHSCOPE_RERANK_TOP_N, len(documents)),
            instruct=self.INSTRUCT,
            allow_real_api=allow_real_api,
            request_id=understanding.request_id,
        )
        if not provider.success:
            diagnostics = self._fallback_diagnostics(original, fallback, provider.status, understanding)
            diagnostics.update({
                "provider_status": provider.status,
                "model": provider.model,
                "request_id_hash": provider.request_id_hash,
                "latency_ms": provider.latency_ms,
                "cache_hit": provider.cache_hit,
                "circuit_breaker_state": provider.circuit_breaker_state,
                "rerank_documents": [
                    {"candidate_id": item.candidate_id, "text_hash": item.text_hash, "text_length": item.text_length}
                    for item in documents
                ],
                "query_hash": query.text_hash,
            })
            return DedicatedRerankResult(fallback, diagnostics)

        returned_indexes = [item.index for item in provider.results]
        returned = set(returned_indexes)
        ranked: list[QueryAwareCandidate] = []
        score_by_id: dict[str, float] = {}
        for item in provider.results:
            source = original[item.index]
            score_by_id[source.candidate_id] = item.relevance_score
            ranked.append(replace(source, rerank_score=item.relevance_score, final_score=item.relevance_score))
        ranked.extend(original[index] for index in range(len(original)) if index not in returned)
        original_ids = [item.candidate_id for item in original]
        ranked_ids = [item.candidate_id for item in ranked]
        if len(ranked_ids) != len(original_ids) or set(ranked_ids) != set(original_ids):
            diagnostics = self._fallback_diagnostics(original, fallback, "QWEN3_RERANK_BOUNDARY_VIOLATION", understanding)
            return DedicatedRerankResult(fallback, diagnostics)
        pre_rank = {candidate_id: index for index, candidate_id in enumerate(original_ids, start=1)}
        post_rank = {candidate_id: index for index, candidate_id in enumerate(ranked_ids, start=1)}
        source_unchanged = all(
            self._source_snapshot(original[original_ids.index(item.candidate_id)]) == self._source_snapshot(item)
            for item in ranked
        )
        diagnostics = {
            "executed": True,
            "success": True,
            "provider": self.settings.RAG_DEDICATED_RERANK_PROVIDER,
            "provider_status": provider.status,
            "model": provider.model,
            "instruct_version": self.INSTRUCT_VERSION,
            "request_id_hash": provider.request_id_hash,
            "query_hash": query.text_hash,
            "latency_ms": provider.latency_ms,
            "cache_hit": provider.cache_hit,
            "circuit_breaker_state": provider.circuit_breaker_state,
            "fallback": False,
            "fallback_reason": None,
            "fallback_order_preserved": True,
            "candidates_in": len(original),
            "candidates_out": len(ranked),
            "candidate_additions": 0,
            "candidate_removals": 0,
            "source_modifications": 0 if source_unchanged else 1,
            "citation_modifications": 0,
            "benchmark_labels_used": False,
            "expected_ids_used": False,
            "rerank_documents": [
                {"candidate_id": item.candidate_id, "text_hash": item.text_hash, "text_length": item.text_length}
                for item in documents
            ],
            "rankings": [
                {
                    "candidate_id": candidate_id,
                    "pre_rerank_rank": pre_rank[candidate_id],
                    "rerank_rank": post_rank[candidate_id],
                    "rerank_score": score_by_id.get(candidate_id),
                    "model": provider.model,
                    "instruct_version": self.INSTRUCT_VERSION,
                    "text_hash": documents[pre_rank[candidate_id] - 1].text_hash,
                    "provider_status": provider.status,
                    "fallback": False,
                    "fallback_reason": None,
                    "latency_ms": provider.latency_ms,
                }
                for candidate_id in ranked_ids
            ],
        }
        return DedicatedRerankResult(ranked, diagnostics)

    def _fallback_diagnostics(
        self,
        candidates: list[QueryAwareCandidate],
        fallback: list[QueryAwareCandidate],
        reason: str,
        understanding: QueryUnderstandingResult,
    ) -> dict[str, Any]:
        candidate_ids = [item.candidate_id for item in candidates]
        fallback_ids = [item.candidate_id for item in fallback]
        return {
            "executed": False,
            "success": False,
            "provider": self.settings.RAG_DEDICATED_RERANK_PROVIDER,
            "provider_status": reason,
            "model": self.settings.RAG_DEDICATED_RERANK_MODEL,
            "instruct_version": self.INSTRUCT_VERSION,
            "request_id_hash": hashlib.sha256(understanding.request_id.encode("utf-8")).hexdigest(),
            "fallback": True,
            "fallback_reason": reason,
            "fallback_order_preserved": fallback_ids == [item.candidate_id for item in fallback],
            "candidates_in": len(candidates),
            "candidates_out": len(fallback),
            "candidate_additions": len(set(fallback_ids) - set(candidate_ids)),
            "candidate_removals": len(set(candidate_ids) - set(fallback_ids)),
            "source_modifications": 0,
            "citation_modifications": 0,
            "benchmark_labels_used": False,
            "expected_ids_used": False,
            "latency_ms": 0.0,
            "circuit_breaker_state": "CLOSED",
        }

    @staticmethod
    def _source_snapshot(item: QueryAwareCandidate) -> tuple:
        return (
            item.content,
            item.document_id,
            item.chunk_id,
            tuple(sorted(item.source_channels)),
            tuple(item.source_chunk_ids),
            repr(sorted((item.source_locator or {}).items())),
        )
