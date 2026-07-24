from __future__ import annotations

import re
import time

from app.core.config import Settings
from app.schemas.retrieval import RetrievalReference, RetrievedChunk
from app.schemas.retrieval_scope import (
    CHINESE_ENGINEERING_PILOT_SCOPE_ID,
    HUAWEI_SUN2000_COMPETITION_SCOPE_ID,
)
from app.services.citation_validation_service import CitationValidationService
from app.services.hybrid_retrieval_service import HybridScoredCandidate
from app.services.retrieval_pipeline_context import RetrievalPipelineContext


class RetrievalEvidenceGate:
    """Apply evidence sufficiency, exact-anchor and citation-validity gates."""

    def __init__(
        self,
        *,
        settings: Settings,
        citation_service: CitationValidationService,
    ) -> None:
        self.settings = settings
        self.citation_service = citation_service

    def apply(self, context: RetrievalPipelineContext) -> None:
        context.insufficient_evidence, context.abstention_reason = self._should_abstain(
            context.query_understanding,
            context.surfaced_candidates,
        )
        understanding = context.query_understanding
        recognised_evidence = any(
            (
                understanding.device_models,
                understanding.fault_codes,
                understanding.fault_names,
                understanding.component_terms,
                understanding.symptom_terms,
                understanding.safety_terms,
                understanding.kg_alias_terms,
                understanding.document_type_filters,
            )
        )
        if (
            context.resolved_request.scope_id
            in {
                CHINESE_ENGINEERING_PILOT_SCOPE_ID,
                HUAWEI_SUN2000_COMPETITION_SCOPE_ID,
            }
            and not recognised_evidence
        ):
            context.insufficient_evidence = True
            context.abstention_reason = "unrecognised_query_in_scope"
        if context.insufficient_evidence:
            context.surfaced_candidates = []

        context.retrieved_chunks = [
            self._candidate_to_retrieved_chunk(candidate)
            for candidate in context.surfaced_candidates
        ]
        context.references = self._build_references(context.retrieved_chunks)
        citation_started = time.perf_counter()
        context.citation_validation = self.citation_service.validate(
            context.references,
            candidate_chunk_ids={item.chunk_id for item in context.retrieved_chunks},
            scope=context.retrieval_scope,
        )
        context.latency_breakdown["citation_validation"] = (
            time.perf_counter() - citation_started
        ) * 1000

    def _should_abstain(
        self,
        analysis,
        candidates: list[HybridScoredCandidate],
    ) -> tuple[bool, str | None]:
        if not candidates:
            return True, "no_verified_candidates"
        if any(
            term in analysis.normalized_query
            for term in ("������", "δ��¼", "δ֪�ͺ�", "δ֪�澯", "û�����")
        ):
            return True, "explicit_no_answer_intent"
        evidence_text = " ".join(
            " ".join(
                (
                    item.document.title or "",
                    item.document.product_series or "",
                    item.document.model or "",
                    " ".join(
                        str(value)
                        for value in (
                            (item.document.metadata_json or {}).get("device_models") or []
                        )
                    ),
                    " ".join(
                        str(value)
                        for value in (
                            (item.chunk.metadata_json or {}).get("fault_codes") or []
                        )
                    ),
                    item.chunk.section_title or "",
                    item.chunk.content or "",
                )
            )
            for item in candidates[:5]
        ).lower()
        if analysis.device_models and not any(
            model.lower() in evidence_text for model in analysis.device_models
        ):
            return True, "exact_device_model_not_supported"
        if analysis.fault_codes and not any(
            code.lower() in evidence_text for code in analysis.fault_codes
        ):
            return True, "exact_fault_code_not_supported"
        top_score = float(candidates[0].score)
        second_score = float(candidates[1].score) if len(candidates) > 1 else 0.0
        if top_score < self.settings.RETRIEVAL_ABSTENTION_MIN_SCORE:
            return True, "top_score_below_abstention_threshold"
        if (
            top_score < 0.55
            and len(candidates) > 1
            and top_score - second_score < self.settings.RETRIEVAL_ABSTENTION_MIN_MARGIN
        ):
            return True, "insufficient_score_margin"
        return False, None

    @staticmethod
    def _candidate_to_retrieved_chunk(
        candidate: HybridScoredCandidate,
    ) -> RetrievedChunk:
        chunk = candidate.chunk
        document = candidate.document
        return RetrievedChunk(
            chunk_id=chunk.id,
            document_id=document.id,
            document_title=document.title,
            chunk_index=chunk.chunk_index,
            section_title=chunk.section_title,
            page_number=chunk.page_number,
            content=chunk.content,
            score=candidate.score,
            manufacturer=document.manufacturer,
            product_series=document.product_series,
            device_type=document.device_type,
            document_type=document.document_type,
            source=document.source,
            created_at=chunk.created_at,
            keyword_score=candidate.keyword_score,
            vector_score=candidate.vector_score,
            vector_raw_score=candidate.vector_raw_score,
            hybrid_score=candidate.hybrid_score,
            exact_model_boost=candidate.exact_model_boost,
            exact_fault_code_boost=candidate.exact_fault_code_boost,
            heading_boost=candidate.heading_boost,
            rrf_score=candidate.rrf_score,
            rerank_score=candidate.rerank_score,
            final_score=candidate.final_score,
            fallback_used=candidate.fallback_used,
            filter_summary=candidate.filter_summary,
            retrieval_source=candidate.retrieval_source,
            vector_backend=candidate.vector_backend,
        )

    def _build_references(
        self,
        chunks: list[RetrievedChunk],
    ) -> list[RetrievalReference]:
        return [
            RetrievalReference(
                document_id=chunk.document_id,
                document_title=chunk.document_title,
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                quote=self._quote(chunk.content),
                manufacturer=chunk.manufacturer,
                product_series=chunk.product_series,
                device_type=chunk.device_type,
                document_type=chunk.document_type,
                source=chunk.source,
                score=chunk.score,
            )
            for chunk in chunks
        ]

    @staticmethod
    def _quote(content: str) -> str:
        compact = re.sub(r"\s+", " ", content).strip()
        return compact[:180]
