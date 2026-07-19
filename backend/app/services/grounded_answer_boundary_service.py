from __future__ import annotations

from app.schemas.query_understanding import ClarificationDecision, QueryUnderstandingResult
from app.services.retrieval_confidence_service import RetrievalConfidenceResult
from app.services.rrf_fusion_service import QueryAwareCandidate


class GroundedAnswerBoundaryService:
    """Expose evidence categories without converting retrieval hypotheses into facts."""

    def build(
        self,
        *,
        understanding: QueryUnderstandingResult,
        clarification: ClarificationDecision,
        confidence: RetrievalConfidenceResult,
        candidates: list[QueryAwareCandidate],
    ) -> dict:
        evidence = [{
            "chunk_id": item.chunk_id,
            "document_title": item.document_title,
            "section_title": item.section_title,
            "page_number": item.page_number,
            "quote": self._quote(item.content),
        } for item in candidates[:3]]
        possible = evidence if confidence.status == "MULTIPLE_POSSIBILITIES" else []
        recommended = []
        if confidence.status == "ANSWERABLE" and understanding.primary_intent in {"TROUBLESHOOTING", "PROCEDURE", "VERIFICATION"}:
            recommended = evidence
        safety = [item for item in evidence if any(term in item["quote"] for term in ("警告", "危险", "断电", "触电", "高压", "禁止"))]
        return {
            "confirmed_evidence": evidence if confidence.status == "ANSWERABLE" else [],
            "possible_explanations": possible,
            "recommended_checks": recommended,
            "safety_warnings": safety,
            "clarifying_question": clarification.questions[0] if clarification.questions else None,
            "insufficient_evidence_notice": (
                "当前中文官方资料中没有足够证据，未生成维修结论或高风险操作步骤。"
                if confidence.status == "INSUFFICIENT_EVIDENCE" else None
            ),
            "hypotheses_promoted_to_fact": False,
            "unsupported_repair_instructions": 0,
        }

    @staticmethod
    def _quote(content: str) -> str:
        compact = " ".join((content or "").split())
        return compact[:240]
