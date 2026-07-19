from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import dataclass
from typing import Callable

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.repositories.retrieval_repository import RetrievalRepository
from app.schemas.query_understanding import QueryUnderstandingResult
from app.schemas.retrieval_plan import RetrievalPlan
from app.schemas.retrieval_scope import RetrievalScope
from app.services.rrf_fusion_service import QueryAwareCandidate
from app.services.semantic_unit_retrieval_service import SemanticUnitRetrievalService
from app.services.embedding_service import EmbeddingService, EmbeddingServiceError
from app.services.vector_index_service import VectorIndexService
from app.services.bounded_retrieval_executor import BoundedRetrievalExecutor
from app.services.candidate_hydration_service import CandidateHydrationService
from app.services.evidence_identity_batch_resolver import EvidenceIdentityBatchResolver
from app.services.query_signal_extraction_service import QuerySignalExtractionService


@dataclass(slots=True)
class MultiQueryRetrievalResult:
    rankings: dict[str, list[QueryAwareCandidate]]
    actual_channels: list[str]
    channel_counts: dict[str, int]
    diagnostics: dict
    executed_channels: list[str]
    nonempty_channels: list[str]
    failed_channels: list[str]
    fallback_channels: list[str]


class MultiQueryRetrievalService:
    """Run query variants across isolated channels with one immutable scope."""

    def __init__(
        self,
        *,
        allow_real_api: bool,
        channel_fetcher: Callable[[str, str, str], list[QueryAwareCandidate]] | None = None,
    ):
        self.settings = get_settings()
        self.allow_real_api = bool(allow_real_api and self.settings.TASK25B_ALLOW_REAL_API)
        self.channel_fetcher = channel_fetcher

    def retrieve(
        self,
        *,
        plan: RetrievalPlan,
        understanding: QueryUnderstandingResult,
        scope: RetrievalScope,
        precomputed_query_vectors: dict[str, list[float]] | None = None,
        precomputed_embedding_ms: float = 0.0,
        precomputed_embedding_calls: int = 0,
    ) -> MultiQueryRetrievalResult:
        if plan.required_scope != scope.scope_id:
            raise ValueError("retrieval plan scope mismatch")
        jobs: list[tuple[str, str, str]] = []
        variant_types = {item.query: item.variant_type for item in plan.query_variants}
        for channel in plan.requested_channels:
            for query in plan.channel_queries.get(channel, []):
                jobs.append((channel, query, variant_types.get(query, "ORIGINAL")))
        started = time.perf_counter()
        rankings: dict[str, list[QueryAwareCandidate]] = {}
        errors: dict[str, str] = {}
        channel_latency: dict[str, float] = {}
        channel_traces: dict[str, dict] = {}
        keyword_hydration = None
        keyword_hydration_started = time.perf_counter()
        if (
            self.channel_fetcher is None
            and self.settings.RAG_SCOPE_BATCH_HYDRATION_ENABLED
            and any(channel in {"EXACT_KEYWORD", "SCOPED_KEYWORD", "KG_ALIAS"} for channel, _query, _type in jobs)
        ):
            with SessionLocal() as hydration_db:
                keyword_hydration = CandidateHydrationService(hydration_db).load_scope_candidates(scope)
        keyword_hydration_ms = round((time.perf_counter() - keyword_hydration_started) * 1000, 3)
        embedding_started = time.perf_counter()
        query_vectors: dict[str, list[float]] = dict(precomputed_query_vectors or {})
        embedding_calls = int(precomputed_embedding_calls)
        embedding_error: str | None = None
        vector_queries = list(dict.fromkeys(
            query
            for channel, query, _ in jobs
            if channel in {"RAW_VECTOR", "SEMANTIC_UNIT"}
        ))
        missing_vector_queries = [query for query in vector_queries if query not in query_vectors]
        if self.allow_real_api and missing_vector_queries:
            try:
                embedded = EmbeddingService(allow_real_api=True).embed_texts(
                    missing_vector_queries, provider=self.settings.EMBEDDING_PROVIDER
                )
                query_vectors.update(zip(missing_vector_queries, embedded.vectors))
                embedding_calls += int(embedded.metadata.get("batch_count") or 1)
            except EmbeddingServiceError as exc:
                embedding_error = type(exc).__name__
        embedding_ms = round(precomputed_embedding_ms + (time.perf_counter() - embedding_started) * 1000, 3)
        executor = BoundedRetrievalExecutor(max_concurrency=self.settings.RAG_MAX_QUERY_VARIANT_CONCURRENCY)
        execution = executor.execute(
            jobs,
            lambda job: self._timed_fetch(
                job,
                understanding=understanding,
                scope=scope,
                top_k=plan.channel_candidate_budgets.get(job[0], plan.candidate_top_k),
                query_vector=query_vectors.get(job[1]),
                anchor_types=plan.anchor_types,
                hydrated_keyword_rows=(keyword_hydration.keyword_rows if keyword_hydration is not None else None),
            ),
        )
        for index, (channel, _query, query_type) in enumerate(jobs):
            key = f"{channel}:{query_type}:{index}"
            if index in execution.errors:
                rankings[key] = []
                errors[key] = execution.errors[index]
                continue
            rankings[key], elapsed_ms, trace = execution.values[index]
            channel_latency[channel] = max(channel_latency.get(channel, 0.0), elapsed_ms)
            if trace:
                channel_traces[key] = trace
        identity_diagnostics = EvidenceIdentityBatchResolver().resolve(rankings)
        rankings, aggregation_diagnostics = self._enforce_channel_identity_budget(
            rankings,
            limit=plan.per_channel_identity_limit,
            query_weights=plan.query_weights,
        )
        actual_channels = sorted({key.split(":", 1)[0] for key, values in rankings.items() if values})
        executed_channels = sorted({key.split(":", 1)[0] for key in rankings if key not in errors})
        failed_channels = sorted({key.split(":", 1)[0] for key in errors})
        counts = Counter()
        for key, values in rankings.items():
            counts[key.split(":", 1)[0]] += len(values)
        return MultiQueryRetrievalResult(
            rankings=rankings,
            actual_channels=actual_channels,
            channel_counts=dict(sorted(counts.items())),
            diagnostics={
                "jobs": len(jobs),
                "parallel": True,
                "bounded": True,
                "max_query_variant_concurrency": execution.max_workers,
                "errors": errors,
                "scope": scope.scope_id,
                "scope_expanded": False,
                "channel_latency_ms": channel_latency,
                "embedding_ms": embedding_ms,
                "embedding_calls": embedding_calls,
                "embedding_unique_queries": len(vector_queries),
                "embedding_error": embedding_error,
                "candidate_hydration_ms": keyword_hydration_ms,
                "candidate_hydration_sql_count": keyword_hydration.sql_count if keyword_hydration else 0,
                "candidate_hydration_rows": len(keyword_hydration.rows) if keyword_hydration else 0,
                "candidate_hydration_cache_hit": keyword_hydration.cache_hit if keyword_hydration else False,
                "candidate_hydration_cache_revision": keyword_hydration.cache_revision if keyword_hydration else None,
                "evidence_identity_batch": identity_diagnostics,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                "raw_vector_trace": {
                    key: value for key, value in channel_traces.items() if key.startswith("RAW_VECTOR:")
                },
                "executed_channels": executed_channels,
                "nonempty_channels": actual_channels,
                "failed_channels": failed_channels,
                "fallback_channels": failed_channels,
                "channel_identity_aggregation": aggregation_diagnostics,
            },
            executed_channels=executed_channels,
            nonempty_channels=actual_channels,
            failed_channels=failed_channels,
            fallback_channels=failed_channels,
        )

    def _timed_fetch(
        self,
        job,
        *,
        understanding,
        scope,
        top_k,
        query_vector,
        anchor_types,
        hydrated_keyword_rows,
    ):
        started = time.perf_counter()
        channel, query, query_type = job
        if channel == "RAW_VECTOR" and self.channel_fetcher is None:
            values, trace = self._raw_vector_with_trace(
                query, query_type, understanding, scope, top_k, query_vector,
            )
        else:
            values, trace = self._fetch(
                channel, query, query_type, understanding, scope, top_k, query_vector,
                anchor_types, hydrated_keyword_rows,
            ), {}
        return values, round((time.perf_counter() - started) * 1000, 3), trace

    def _fetch(
        self,
        channel: str,
        query: str,
        query_type: str,
        understanding: QueryUnderstandingResult,
        scope: RetrievalScope,
        top_k: int,
        query_vector: list[float] | None,
        anchor_types: list[str],
        hydrated_keyword_rows=None,
    ) -> list[QueryAwareCandidate]:
        if self.channel_fetcher is not None:
            return self.channel_fetcher(channel, query, query_type)
        if channel in {"EXACT_KEYWORD", "SCOPED_KEYWORD", "KG_ALIAS"}:
            return self._keyword(
                channel, query, query_type, understanding, scope, top_k,
                hydrated_keyword_rows=hydrated_keyword_rows,
            )
        if channel == "RAW_VECTOR":
            return self._raw_vector(query, query_type, understanding, scope, top_k, query_vector)
        if channel == "SEMANTIC_UNIT":
            return self._semantic(query, query_type, understanding, scope, top_k, query_vector, anchor_types)
        return []

    def _keyword(self, channel, query, query_type, understanding, scope, top_k, *, hydrated_keyword_rows=None):
        keywords = self._keywords(query, understanding, exact=channel == "EXACT_KEYWORD")
        if hydrated_keyword_rows is not None:
            hits = CandidateHydrationService.rank_keyword_candidate_hits(
                hydrated_keyword_rows, keywords=keywords, candidate_limit=top_k,
            )
        else:
            with SessionLocal() as db:
                hits = RetrievalRepository(db).list_scored_knowledge_candidates(
                    keywords=keywords,
                    device_type=None,
                    candidate_limit=top_k,
                    scope=scope,
                )
        result = []
        for hit in hits:
            candidate = self._candidate(
                hit.chunk, hit.document, channel, query_type, hit.normalized_relevance_score,
                understanding, scope, keyword_hit=hit,
            )
            result.append(candidate)
        return result

    def _raw_vector(self, query, query_type, understanding, scope, top_k, query_vector):
        values, _ = self._raw_vector_with_trace(query, query_type, understanding, scope, top_k, query_vector)
        return values

    def _raw_vector_with_trace(self, query, query_type, understanding, scope, top_k, query_vector):
        if not self.allow_real_api or query_vector is None:
            return [], {
                "requested": True, "executed": False, "nonempty": False,
                "fallback_reason": "real_api_disabled_or_embedding_missing",
                "collection_name": scope.collection_name, "partition_name": scope.partition_name,
            }
        with SessionLocal() as db:
            hits, diagnostics = VectorIndexService(
                db,
                allow_real_api=True,
                collection_name=scope.collection_name,
                namespace=scope.partition_name,
            ).search(
                query,
                top_k=top_k,
                filters={},
                scope=scope,
                query_vector=query_vector,
            )
            values = [self._candidate(hit.chunk, hit.document, "RAW_VECTOR", query_type, hit.score, understanding, scope) for hit in hits]
            return values, {
                "requested": True,
                "executed": bool((diagnostics.get("external_call_counts") or {}).get("dashvector")),
                "nonempty": bool(values),
                "embedding_available": query_vector is not None,
                "collection_name": diagnostics.get("collection_name") or scope.collection_name,
                "partition_name": diagnostics.get("partition_name") or scope.partition_name,
                "raw_hits": diagnostics.get("raw_vector_hits", 0),
                "post_filter_hits": diagnostics.get("verified_hits", len(values)),
                "mapped_candidate_count": len(values),
                "none_filters_removed": diagnostics.get("none_filters_removed") or [],
                "filtered_reason_counts": diagnostics.get("filtered_reason_counts") or {},
                "raw_vector_ids_hash": diagnostics.get("raw_vector_ids_hash"),
                "verified_chunk_ids_hash": diagnostics.get("verified_chunk_ids_hash"),
                "fallback_reason": diagnostics.get("fallback_reason"),
            }

    def _semantic(self, query, query_type, understanding, scope, top_k, query_vector, anchor_types):
        if not self.allow_real_api or query_vector is None:
            return []
        with SessionLocal() as db:
            result = SemanticUnitRetrievalService(
                db,
                allow_real_api=True,
                collection_name=scope.collection_name,
                namespace="pilot_r5_query_aware",
            ).search(
                query,
                scope=scope,
                top_k=top_k,
                per_type_top_k=min(40, top_k),
                query_vector=query_vector,
                requested_anchor_types=anchor_types,
            )
            candidates = []
            for unit in result.candidates:
                if not unit.source_chunks:
                    continue
                chunk = unit.source_chunks[0]
                candidate = self._candidate(
                    chunk, unit.document, "SEMANTIC_UNIT", query_type, unit.final_unit_score, understanding, scope,
                )
                candidate.semantic_unit_id = unit.semantic_unit_id
                candidate.candidate_id = f"su:{unit.semantic_unit_id}"
                candidate.source_chunk_ids = [str(item.id) for item in unit.source_chunks]
                candidate.source_locator = unit.source_locator
                candidates.append(candidate)
            return candidates

    @staticmethod
    def _keywords(query: str, understanding: QueryUnderstandingResult, *, exact: bool) -> list[str]:
        model_parts = [
            part
            for model in understanding.device_models
            for part in re.split(r"[-_/\s]+", model)
            if len(part) >= 2
        ]
        explicit = [
            *understanding.device_models, *understanding.alarm_codes, *understanding.alarm_names,
            *model_parts, *understanding.components, *understanding.symptoms,
        ]
        quoted_phrases = [
            value.strip()
            for value in re.findall(r"[“\"《]([^”\"》]{3,96})[”\"》]", query)
            if value.strip()
        ]
        lexical_terms = QuerySignalExtractionService.retrieval_terms(query, limit=48)
        values = list(dict.fromkeys([*explicit, *quoted_phrases, *lexical_terms]))
        if exact:
            return values[:112] or [query]
        return values[:128] or [query]

    @staticmethod
    def _candidate(chunk, document, channel, query_type, score, understanding, scope, *, keyword_hit=None):
        haystack = " ".join((document.title or "", document.model or "", chunk.section_title or "", chunk.content or "")).lower()
        specific_models = [
            value for value in understanding.device_models
            if MultiQueryRetrievalService._compact_identifier(value) != "sun2000"
        ]
        model_match = bool(specific_models) and any(
            MultiQueryRetrievalService._contains_exact_identifier(haystack, value)
            for value in specific_models
        )
        alarm_terms = [*understanding.alarm_codes, *understanding.alarm_names]
        alarm_match = bool(alarm_terms) and any(
            MultiQueryRetrievalService._contains_exact_term(haystack, value) for value in alarm_terms
        )
        metadata = chunk.metadata_json or {}
        locator = metadata.get("source_locator") or {
            "section": chunk.section_title,
            "page_start": chunk.page_number,
            "page_end": chunk.page_number,
            "source_chunk_ids": [str(chunk.id)],
        }
        score_key = f"{channel}:{query_type}"
        return QueryAwareCandidate(
            candidate_id=str(chunk.id),
            chunk_id=str(chunk.id),
            document_id=str(document.id),
            document_title=document.title,
            content=chunk.content or "",
            section_title=chunk.section_title,
            page_number=chunk.page_number,
            chunk=chunk,
            document=document,
            source_channels={channel},
            source_query_types={query_type},
            raw_scores={score_key: float(score)},
            exact_model_match=model_match,
            exact_alarm_match=alarm_match,
            source_chunk_ids=[str(chunk.id)],
            source_locator=locator,
            scope_validation_passed=document.id in scope.allowed_document_ids,
            raw_relevance_score=float(keyword_hit.raw_relevance_score) if keyword_hit else float(score),
            normalized_relevance_score=float(keyword_hit.normalized_relevance_score) if keyword_hit else float(score),
            repository_rank=keyword_hit.repository_rank if keyword_hit else None,
            matched_fields=set(keyword_hit.matched_fields) if keyword_hit else set(),
            matched_tokens=set(keyword_hit.matched_tokens) if keyword_hit else set(),
            exact_phrase_matches=set(keyword_hit.exact_phrase_matches) if keyword_hit else set(),
            exact_body_phrase_matches=set(keyword_hit.exact_body_phrase_matches) if keyword_hit else set(),
            score_source=keyword_hit.score_source if keyword_hit else channel.lower(),
            score_fallback_used=bool(keyword_hit.score_fallback_used) if keyword_hit else False,
            score_provenance={score_key: {
                "raw_relevance_score": float(keyword_hit.raw_relevance_score) if keyword_hit else float(score),
                "normalized_relevance_score": float(keyword_hit.normalized_relevance_score) if keyword_hit else float(score),
                "repository_rank": keyword_hit.repository_rank if keyword_hit else None,
                "matched_fields": list(keyword_hit.matched_fields) if keyword_hit else [],
                "matched_tokens": list(keyword_hit.matched_tokens) if keyword_hit else [],
                "exact_phrase_matches": list(keyword_hit.exact_phrase_matches) if keyword_hit else [],
                "exact_body_phrase_matches": list(keyword_hit.exact_body_phrase_matches) if keyword_hit else [],
                "score_source": keyword_hit.score_source if keyword_hit else channel.lower(),
                "score_fallback_used": bool(keyword_hit.score_fallback_used) if keyword_hit else False,
                "score_breakdown": dict(keyword_hit.score_breakdown) if keyword_hit else {},
            }},
        )

    @staticmethod
    def _compact_identifier(value: str) -> str:
        return "".join(
            character for character in str(value).casefold()
            if character.isalnum() or character == "+"
        )

    @staticmethod
    def _contains_exact_term(haystack: str, value: str) -> bool:
        term = str(value).strip().lower()
        if not term:
            return False
        if term.isdigit():
            return re.search(rf"(?<!\d){re.escape(term)}(?!\d)", haystack) is not None
        return term in haystack

    @staticmethod
    def _contains_exact_identifier(haystack: str, value: str) -> bool:
        parts = [part for part in re.split(r"[-_/\s]+", str(value).strip()) if part]
        if not parts:
            return False
        separator = r"[-_/\s]*"
        pattern = separator.join(re.escape(part) for part in parts)
        if re.search(rf"(?<![A-Za-z0-9+]){pattern}(?![A-Za-z0-9+])", haystack, re.I) is not None:
            return True
        compact_value = MultiQueryRetrievalService._compact_identifier(value)
        compact_haystack = MultiQueryRetrievalService._compact_identifier(haystack)
        if not compact_value:
            return False
        start = compact_haystack.find(compact_value)
        while start >= 0:
            following = compact_haystack[start + len(compact_value):]
            if not (compact_value.endswith("h0") and following.startswith("+")):
                return True
            start = compact_haystack.find(compact_value, start + 1)
        return False

    @staticmethod
    def _enforce_channel_identity_budget(
        rankings: dict[str, list[QueryAwareCandidate]], *, limit: int,
        query_weights: dict[str, float] | None = None,
    ) -> tuple[dict[str, list[QueryAwareCandidate]], dict[str, dict[str, int]]]:
        by_channel: dict[str, list[tuple[str, list[QueryAwareCandidate]]]] = {}
        for key, values in rankings.items():
            by_channel.setdefault(key.split(":", 1)[0], []).append((key, values))
        diagnostics: dict[str, dict[str, object]] = {}
        filtered = dict(rankings)
        query_weights = query_weights or {}
        for channel, channel_rankings in by_channel.items():
            aggregate_scores: dict[str, float] = {}
            best_rank: dict[str, int] = {}
            best_query_types: dict[str, str] = {}
            for key, values in channel_rankings:
                parts = key.split(":")
                query_type = parts[1] if len(parts) > 1 else "ORIGINAL"
                query_weight = query_weights.get(query_type, 1.0)
                seen: set[str] = set()
                for rank, item in enumerate(values, start=1):
                    identity = item.evidence_equivalence_key or item.evidence_identity or item.candidate_id
                    if identity in seen:
                        continue
                    seen.add(identity)
                    contribution = query_weight * (
                        1.0 / (60 + rank)
                        + 0.012 * max(0.0, min(1.0, item.normalized_relevance_score))
                    )
                    previous = aggregate_scores.get(identity)
                    if previous is None or contribution > previous:
                        aggregate_scores[identity] = contribution
                        best_query_types[identity] = query_type
                    best_rank[identity] = min(rank, best_rank.get(identity, rank))
            allowed = {
                identity for identity, _score in sorted(
                    aggregate_scores.items(), key=lambda pair: (-pair[1], best_rank[pair[0]], pair[0])
                )[:limit]
            }
            for key, values in channel_rankings:
                seen: set[str] = set()
                kept: list[QueryAwareCandidate] = []
                for item in values:
                    identity = item.evidence_equivalence_key or item.evidence_identity or item.candidate_id
                    if identity not in allowed or identity in seen:
                        continue
                    seen.add(identity)
                    kept.append(item)
                filtered[key] = kept
            diagnostics[channel] = {
                "raw_candidate_rows": sum(len(values) for _key, values in channel_rankings),
                "unique_evidence_identities": len(aggregate_scores),
                "retained_evidence_identities": len(allowed),
                "identity_limit": limit,
                "aggregation_mode": "best_score_aware_vote_per_physical_channel",
                "original_query_winners": sum(
                    query_type == "ORIGINAL" for query_type in best_query_types.values()
                ),
            }
        return filtered, diagnostics
