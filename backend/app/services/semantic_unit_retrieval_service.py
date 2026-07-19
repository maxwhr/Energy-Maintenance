from __future__ import annotations

import hashlib
import json
import time
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import KnowledgeChunk, KnowledgeDocument
from app.repositories.semantic_anchor_repository import SemanticAnchorRepository
from app.schemas.retrieval_scope import RetrievalScope
from app.services.embedding_service import EmbeddingService, EmbeddingServiceError
from app.services.vector_index_service import VectorIndexService
from app.services.vector_store_adapters.base import VectorStoreAdapterError


@dataclass(frozen=True, slots=True)
class SemanticUnitCandidate:
    semantic_unit_id: str
    semantic_unit_type: str
    source_chunks: list[KnowledgeChunk]
    document: KnowledgeDocument
    anchor_types: list[str]
    anchor_scores: dict[str, float]
    vector_similarity: float
    final_unit_score: float
    source_locator: dict


@dataclass(frozen=True, slots=True)
class SemanticUnitSearchResult:
    candidates: list[SemanticUnitCandidate]
    diagnostics: dict


class SemanticUnitRetrievalService:
    """Intent-aware retrieval over source-grounded maintenance semantic units.

    Query text is used only at retrieval time. It is never persisted in an
    anchor, and canonical semantic text is never returned as citation evidence.
    """

    VERSION = "task25b_r3_dev_r4_semantic_unit_v1"
    PARTITION = "pilot_r4_grounded"
    ALLOWED_PARTITIONS = {"pilot_r4_grounded", "pilot_r5_query_aware"}
    INTENT_ANCHORS = {
        "symptom": ("SYMPTOM", "ALARM", "COMPONENT"),
        "cause": ("CAUSE", "SYMPTOM", "ALARM"),
        "action": ("ACTION", "PROCEDURE", "SAFETY"),
        "prerequisite": ("PREREQUISITE", "SAFETY", "PROCEDURE"),
        "verification": ("VERIFICATION", "PROCEDURE"),
        "communication": ("COMMUNICATION", "SYMPTOM", "ACTION"),
    }
    INTENT_TERMS = {
        "communication": ("通信", "联网", "离线", "网络", "网线", "rs485", "modbus", "以太网", "串口"),
        "prerequisite": ("前提", "前置", "准备", "之前", "条件", "需要先"),
        "verification": ("如何确认", "怎么确认", "验证", "完成了吗", "是否恢复", "确认完成"),
        "cause": ("为什么", "原因", "导致", "怎么回事", "为何"),
        "action": ("怎么办", "怎么处理", "如何处理", "如何操作", "怎么修", "步骤", "排查", "检修"),
        "symptom": ("异常", "故障", "告警", "中断", "失败", "离线", "过温", "无响应", "现象"),
    }

    def __init__(
        self, db: Session, *, allow_real_api: bool, collection_name: str,
        namespace: str = PARTITION, tuning: dict | None = None,
    ):
        if namespace not in self.ALLOWED_PARTITIONS:
            raise ValueError(
                "semantic-unit retrieval is restricted to pilot_r4_grounded or pilot_r5_query_aware"
            )
        self.db = db
        self.settings = get_settings()
        self.allow_real_api = allow_real_api
        self.collection_name = collection_name
        self.namespace = namespace
        self.repository = SemanticAnchorRepository(db)
        self.tuning = tuning or {}

    @classmethod
    def classify_intent(cls, query_text: str) -> tuple[str, list[str]]:
        normalized = " ".join(query_text.lower().split())
        if any(term in normalized for term in ("告警标识", "告警代码", "报警代码")):
            return "symptom", ["ALARM", "SYMPTOM", "ACTION"]
        if any(term in normalized for term in ("风险隔离", "安全措施", "安全要求", "触电风险")):
            return "action", ["SAFETY", "ACTION", "PROCEDURE"]
        for intent in ("communication", "prerequisite", "verification", "cause", "action", "symptom"):
            if any(term in normalized for term in cls.INTENT_TERMS[intent]):
                return intent, list(cls.INTENT_ANCHORS[intent])
        return "symptom", list(cls.INTENT_ANCHORS["symptom"])

    @staticmethod
    def focus_query_representation(query_text: str) -> str:
        normalized = " ".join(query_text.split())
        patterns = (
            r"出现(.+?)相关", r"进行(.+?)相关", r"处理(.+?)相关", r"面对(.+?)相关",
            r"针对(.+?)相关", r"表现为(.+?)时",
        )
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if match and 2 <= len(match.group(1).strip()) <= 80:
                return match.group(1).strip(" ，。；：、")
        return normalized

    @staticmethod
    def merge_unit_records(records: Iterable[tuple[str, str, float, float]]) -> dict[str, dict]:
        merged: dict[str, dict] = {}
        for unit_id, anchor_type, score, raw_score in records:
            item = merged.setdefault(unit_id, {"scores": {}, "raw_scores": {}, "hits": 0})
            item["scores"][anchor_type] = max(float(score), item["scores"].get(anchor_type, 0.0))
            item["raw_scores"][anchor_type] = min(float(raw_score), item["raw_scores"].get(anchor_type, float("inf")))
            item["hits"] += 1
        return merged

    @staticmethod
    def final_score(
        anchor_scores: dict[str, float], requested_types: list[str], *,
        consistency_step: float = 0.03, primary_intent_boost: float = 0.025,
    ) -> float:
        if not anchor_scores:
            return 0.0
        maximum = max(anchor_scores.values())
        matched = len(set(anchor_scores).intersection(requested_types))
        consistency = min(0.08, max(0, matched - 1) * consistency_step)
        intent_boost = primary_intent_boost if requested_types and requested_types[0] in anchor_scores else 0.0
        return round(min(1.0, maximum + consistency + intent_boost), 8)

    def search(
        self,
        query_text: str,
        *,
        scope: RetrievalScope,
        top_k: int = 50,
        per_type_top_k: int = 50,
        query_vector: list[float] | None = None,
        requested_anchor_types: list[str] | None = None,
    ) -> SemanticUnitSearchResult:
        started = time.perf_counter()
        intent, requested_types = self.classify_intent(query_text)
        override = requested_anchor_types or (self.tuning.get("intent_anchor_overrides") or {}).get(intent)
        if isinstance(override, list) and override:
            requested_types = [str(value) for value in override]
        requested_types = list(dict.fromkeys(requested_types))[:8]
        query_representation = self.focus_query_representation(query_text) if self.tuning.get("focus_query") else query_text
        service = VectorIndexService(
            self.db, allow_real_api=self.allow_real_api,
            collection_name=self.collection_name, namespace=self.namespace,
        )
        config = service._runtime_config(provider=self.settings.EMBEDDING_PROVIDER, vector_backend="dashvector")
        embedding_service = EmbeddingService(allow_real_api=self.allow_real_api)
        try:
            embedding_started = time.perf_counter()
            embedded = None
            vector = query_vector
            if vector is None:
                embedded = embedding_service.embed_query(query_representation, provider=config["embedding_provider"])
                vector = embedded.vectors[0]
            embedding_ms = round((time.perf_counter() - embedding_started) * 1000, 3)
            adapter = service._adapter(config)
            dashvector_started = time.perf_counter()
            with ThreadPoolExecutor(
                max_workers=min(self.settings.RAG_MAX_VECTOR_CONCURRENCY, len(requested_types)),
                thread_name_prefix="typed-semantic-anchor",
            ) as executor:
                futures = {
                    anchor_type: executor.submit(
                        adapter.query_vectors, vector=vector, top_k=per_type_top_k,
                        filters={"object_type": "maintenance_semantic_unit", "anchor_type": anchor_type},
                        request_context={
                            "operation": "SEMANTIC_UNIT",
                            "query_mode": "semantic_unit",
                            "embedding_provider": config["embedding_provider"],
                            "embedding_model": config["embedding_model"],
                            "embedding_dimension": config["embedding_dim"],
                            "score_threshold": self.settings.VECTOR_MIN_SCORE,
                            "index_version": self.settings.EMBEDDING_INDEX_VERSION,
                            "retrieval_config_version": "task25f_r1_coalescing_v2",
                            "scope_fingerprint": hashlib.sha256(
                                json.dumps(
                                    scope.public_dict(),
                                    ensure_ascii=False,
                                    sort_keys=True,
                                    separators=(",", ":"),
                                ).encode("utf-8")
                            ).hexdigest(),
                        },
                    )
                    for anchor_type in requested_types
                }
                typed_hits = {anchor_type: future.result() for anchor_type, future in futures.items()}
            dashvector_ms = round((time.perf_counter() - dashvector_started) * 1000, 3)
        except (EmbeddingServiceError, VectorStoreAdapterError) as exc:
            return SemanticUnitSearchResult([], {
                "actual_route": "grounded_semantic_unit", "fallback_used": False,
                "fallback_reason": f"grounded_semantic_error:{type(exc).__name__}",
                "intent": intent, "requested_anchor_types": requested_types,
                "vector_partition": self.namespace, "stage_latency": {
                    "total_ms": round((time.perf_counter() - started) * 1000, 3),
                },
            })

        vector_ids = [hit.vector_id for hits in typed_hits.values() for hit in hits]
        anchors = self.repository.by_vector_ids(
            collection=config["collection_name"], namespace=self.namespace, vector_ids=vector_ids,
        )
        records: list[tuple[str, str, float, float]] = []
        unit_rows: dict[str, object] = {}
        dropped_wrong_type = 0
        for requested_type, hits in typed_hits.items():
            accepted = 0
            for hit in hits:
                anchor = anchors.get(hit.vector_id)
                if anchor is None or anchor.anchor_type != requested_type:
                    dropped_wrong_type += 1
                    continue
                semantic = (anchor.semantic_fields or {}).get("semantic_unit") or {}
                unit_id = str(semantic.get("semantic_unit_id") or "")
                if not unit_id or semantic.get("quality_status") != "ENGINEERING_VERIFIED_SOURCE_GROUNDED":
                    continue
                records.append((unit_id, requested_type, hit.score, hit.raw_score))
                unit_rows[unit_id] = anchor
                accepted += 1
                if accepted >= per_type_top_k:
                    break
        merged = self.merge_unit_records(records)

        source_ids: set[UUID] = set()
        document_ids: set[UUID] = set()
        for unit_id in merged:
            anchor = unit_rows[unit_id]
            semantic = (anchor.semantic_fields or {}).get("semantic_unit") or {}
            source_ids.update(UUID(value) for value in semantic.get("source_chunk_ids") or [str(anchor.source_chunk_id)])
            document_ids.add(anchor.document_id)
        chunks = {chunk.id: chunk for chunk in self.db.scalars(select(KnowledgeChunk).where(
            KnowledgeChunk.id.in_(source_ids), KnowledgeChunk.status == "active",
        ))} if source_ids else {}
        documents = {document.id: document for document in self.db.scalars(select(KnowledgeDocument).where(
            KnowledgeDocument.id.in_(document_ids), KnowledgeDocument.id.in_(scope.allowed_document_ids),
            KnowledgeDocument.status == "active", KnowledgeDocument.review_status == "approved",
        ))} if document_ids else {}

        candidates: list[SemanticUnitCandidate] = []
        post_scope_dropped = 0
        for unit_id, merged_row in merged.items():
            anchor = unit_rows[unit_id]
            document = documents.get(anchor.document_id)
            semantic = (anchor.semantic_fields or {}).get("semantic_unit") or {}
            source_chunks = [chunks[UUID(value)] for value in semantic.get("source_chunk_ids") or [] if UUID(value) in chunks]
            if document is None or not source_chunks or anchor.language != scope.normalized_language or not anchor.current_version:
                post_scope_dropped += 1
                continue
            scores = {key: round(value, 8) for key, value in merged_row["scores"].items()}
            candidates.append(SemanticUnitCandidate(
                semantic_unit_id=unit_id,
                semantic_unit_type=str(semantic.get("semantic_unit_type") or semantic.get("unit_type") or ""),
                source_chunks=source_chunks,
                document=document,
                anchor_types=sorted(scores),
                anchor_scores=scores,
                vector_similarity=max(scores.values()),
                final_unit_score=self.final_score(
                    scores, requested_types,
                    consistency_step=float(self.tuning.get("typed_consistency_step", 0.03)),
                    primary_intent_boost=float(self.tuning.get("primary_intent_boost", 0.025)),
                ),
                source_locator=semantic.get("source_locator") or anchor.source_locator or {},
            ))
        candidates.sort(key=lambda item: (-item.final_unit_score, item.semantic_unit_id))
        if self.tuning.get("candidate_round_robin") and len(candidates) > top_k:
            by_type = {
                anchor_type: sorted(
                    [item for item in candidates if anchor_type in item.anchor_scores],
                    key=lambda item: (-item.anchor_scores[anchor_type], item.semantic_unit_id),
                )
                for anchor_type in requested_types
            }
            selected: list[SemanticUnitCandidate] = []
            selected_ids: set[str] = set()
            position = 0
            while len(selected) < top_k and any(position < len(values) for values in by_type.values()):
                for anchor_type in requested_types:
                    values = by_type[anchor_type]
                    if position < len(values) and values[position].semantic_unit_id not in selected_ids:
                        selected.append(values[position]); selected_ids.add(values[position].semantic_unit_id)
                        if len(selected) == top_k:
                            break
                position += 1
            for item in candidates:
                if len(selected) == top_k:
                    break
                if item.semantic_unit_id not in selected_ids:
                    selected.append(item); selected_ids.add(item.semantic_unit_id)
            candidates = sorted(selected, key=lambda item: (-item.final_unit_score, item.semantic_unit_id))
        total_ms = round((time.perf_counter() - started) * 1000, 3)
        diagnostics = {
            "actual_route": "grounded_semantic_unit", "fallback_used": False, "fallback_reason": None,
            "intent": intent, "requested_anchor_types": requested_types,
            "focus_query_used": bool(self.tuning.get("focus_query")),
            "vector_representation": "maintenance_semantic_unit", "vector_partition": self.namespace,
            "typed_anchor_scores_visible": True, "typed_search_count": len(requested_types),
            "candidate_round_robin": bool(self.tuning.get("candidate_round_robin")),
            "raw_anchor_hits": sum(len(hits) for hits in typed_hits.values()),
            "merged_semantic_units": len(candidates), "wrong_type_dropped": dropped_wrong_type,
            "post_scope_dropped": post_scope_dropped,
            "candidate_recall_trace": [
                {
                    "semantic_unit_id": item.semantic_unit_id,
                    "anchor_types": item.anchor_types,
                    "anchor_scores": item.anchor_scores,
                    "final_unit_score": item.final_unit_score,
                    "source_chunk_ids": [str(chunk.id) for chunk in item.source_chunks],
                    "source_locator": item.source_locator,
                }
                for item in candidates[:50]
            ],
            "collection_name": config["collection_name"], "embedding_model": config["embedding_model"],
            "embedding_dimension": config["embedding_dim"],
            "stage_latency": {"embedding_ms": embedding_ms, "dashvector_ms": dashvector_ms, "total_ms": total_ms},
            "external_call_counts": {
                "embedding": 0 if query_vector is not None or (embedded and embedded.metadata.get("cache_hit")) else 1,
                "dashvector": len(requested_types),
            },
        }
        return SemanticUnitSearchResult(candidates[:top_k], diagnostics)
