from __future__ import annotations

import json
import math
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, raiseload

from app.models import KnowledgeChunk, KnowledgeDocument
from app.core.config import get_settings
from app.repositories.retrieval_repository import RetrievalRepository
from app.schemas.retrieval_scope import RetrievalScope
from app.services.retrieval_text_feature_service import RetrievalTextFeatureService, RetrievalTextFeatures


@dataclass(frozen=True, slots=True)
class HydratedKeywordRow:
    chunk: KnowledgeChunk
    document: KnowledgeDocument
    content: str
    section: str
    title: str
    search_blob: str
    features: RetrievalTextFeatures = field(
        default_factory=lambda: RetrievalTextFeatureService.build("")
    )


@dataclass(frozen=True, slots=True)
class CandidateHydrationResult:
    rows: tuple[tuple[KnowledgeChunk, KnowledgeDocument], ...]
    keyword_rows: tuple[HydratedKeywordRow, ...]
    chunks: Mapping[str, KnowledgeChunk]
    documents: Mapping[str, KnowledgeDocument]
    elapsed_ms: float
    sql_count: int
    cache_hit: bool = False
    cache_revision: str = ""


class CandidateHydrationService:
    """Loads the immutable request scope once; ranking performs no repository calls."""

    _scope_cache: dict[tuple, tuple[float, CandidateHydrationResult]] = {}
    _scope_cache_lock = threading.Lock()
    _cache_generation = 0

    def __init__(self, db: Session):
        self.db = db

    @classmethod
    def invalidate_scope_cache(cls) -> None:
        """Invalidate process-local snapshots after a committed corpus change."""
        with cls._scope_cache_lock:
            cls._cache_generation += 1
            cls._scope_cache.clear()

    def load_scope_candidates(self, scope: RetrievalScope) -> CandidateHydrationResult:
        started = time.perf_counter()
        ttl = float(get_settings().RAG_SCOPE_HYDRATION_CACHE_TTL_SECONDS)
        key = (
            scope.scope_id,
            self._cache_generation,
            tuple(str(value) for value in scope.allowed_document_ids),
            scope.required_document_status,
            scope.required_chunk_status,
            scope.normalized_language,
            scope.approved_for_pilot,
            scope.current_version_only,
            scope.include_alternate_language,
            scope.include_test_fixture,
            scope.include_marketing,
        )
        with self._scope_cache_lock:
            now = time.monotonic()
            cached = self._scope_cache.get(key)
            if ttl > 0 and cached and cached[0] > now:
                value = cached[1]
                return CandidateHydrationResult(
                    rows=value.rows,
                    keyword_rows=value.keyword_rows,
                    chunks=value.chunks,
                    documents=value.documents,
                    elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
                    sql_count=0,
                    cache_hit=True,
                    cache_revision=value.cache_revision,
                )
            if cached:
                self._scope_cache.pop(key, None)
            statement = (
                select(KnowledgeChunk, KnowledgeDocument)
                .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
                .where(
                    KnowledgeDocument.parse_status == "parsed",
                    KnowledgeDocument.status == "active",
                    KnowledgeDocument.review_status == "approved",
                    KnowledgeChunk.status == "active",
                    *RetrievalRepository._scope_filters(scope),
                )
                .options(raiseload("*"))
            )
            rows = tuple((row[0], row[1]) for row in self.db.execute(statement).all())
            keyword_rows = []
            for chunk, document in rows:
                content = (chunk.content or "").casefold()
                section = (chunk.section_title or "").casefold()
                title = (document.title or "").casefold()
                summary = (document.summary or "").casefold()
                source = (document.source or "").casefold()
                metadata = json.dumps(
                    document.metadata_json or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).casefold()
                keyword_rows.append(HydratedKeywordRow(
                    chunk=chunk,
                    document=document,
                    content=content,
                    section=section,
                    title=title,
                    search_blob="\n".join((content, section, title, summary, source, metadata)),
                    features=RetrievalTextFeatureService.build(
                        "\n".join((content, section, title, summary, source, metadata))
                    ),
                ))
            cache_revision = self._snapshot_revision(scope, rows)
            result = CandidateHydrationResult(
                rows=rows,
                keyword_rows=tuple(keyword_rows),
                chunks=MappingProxyType({str(chunk.id): chunk for chunk, _document in rows}),
                documents=MappingProxyType({str(document.id): document for _chunk, document in rows}),
                elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
                sql_count=1 if rows or scope.allowed_document_ids else 0,
                cache_hit=False,
                cache_revision=cache_revision,
            )
            if ttl > 0:
                self._scope_cache[key] = (now + ttl, result)
                if len(self._scope_cache) > 4:
                    oldest = min(self._scope_cache, key=lambda item: self._scope_cache[item][0])
                    self._scope_cache.pop(oldest, None)
            return result

    @staticmethod
    def rank_keyword_candidates(
        rows: Sequence[HydratedKeywordRow],
        *,
        keywords: list[str],
        candidate_limit: int,
    ) -> list[tuple[KnowledgeChunk, KnowledgeDocument]]:
        terms = list(dict.fromkeys(str(value).strip().casefold() for value in keywords if str(value).strip()))
        generic_terms = {
            "huawei", "华为", "sun2000", "fusionsolar", "光伏", "逆变器", "光伏逆变器", "设备",
            "如何", "怎么", "怎样", "什么", "是否", "可以", "需要", "应该", "检查", "排查", "处理",
        }
        ranking_terms = [value for value in terms if value not in generic_terms]
        document_frequency = {
            term: sum(term in row.search_blob for row in rows)
            for term in ranking_terms
        }
        row_count = max(1, len(rows))
        compact_terms = {
            CandidateHydrationService._compact_identifier(value)
            for value in keywords
            if str(value).upper().startswith("SUN2000") and str(value).upper() != "SUN2000"
        }
        scored: list[tuple[float, float, int, str, KnowledgeChunk, KnowledgeDocument]] = []
        for row in rows:
            chunk = row.chunk
            document = row.document
            compact_blob = CandidateHydrationService._compact_identifier(row.search_blob)
            compact_match = any(term and term in compact_blob for term in compact_terms)
            if terms and not any(term in row.search_blob for term in terms) and not compact_match:
                continue
            rank = 0.0
            for term in ranking_terms:
                if term not in row.search_blob:
                    continue
                idf = math.log((row_count + 1) / (document_frequency[term] + 1)) + 1.0
                length_weight = 1.0 + min(len(term), 10) / 5.0
                identifier_weight = 2.5 if re.fullmatch(r"[a-z]{0,4}-?\d{3,6}", term, re.I) else 1.0
                field_weight = (
                    (3.2 if term in row.section else 0.0)
                    + (2.4 if term in row.title else 0.0)
                    + (1.0 + min(row.content.count(term), 3) * 0.15 if term in row.content else 0.0)
                )
                rank += idf * length_weight * identifier_weight * field_weight
            if compact_match:
                rank += 80.0
            for term in terms:
                if term in generic_terms and term in row.search_blob:
                    rank += 0.05
            created = document.created_at or datetime.min.replace(tzinfo=timezone.utc)
            timestamp = created.timestamp() if created.tzinfo else created.replace(tzinfo=timezone.utc).timestamp()
            scored.append((rank, timestamp, int(chunk.chunk_index), str(chunk.id), chunk, document))
        scored.sort(key=lambda row: (-row[0], -row[1], row[2], row[3]))
        return [(row[4], row[5]) for row in scored[:candidate_limit]]

    @staticmethod
    def _compact_identifier(value: str) -> str:
        return "".join(character for character in str(value).casefold() if character.isalnum())

    @staticmethod
    def _snapshot_revision(
        scope: RetrievalScope,
        rows: Sequence[tuple[KnowledgeChunk, KnowledgeDocument]],
    ) -> str:
        import hashlib

        values = [scope.scope_id]
        values.extend(
            f"{document.id}:{document.updated_at.isoformat() if document.updated_at else ''}:"
            f"{chunk.id}:{chunk.updated_at.isoformat() if chunk.updated_at else ''}"
            for chunk, document in rows
        )
        return hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()
