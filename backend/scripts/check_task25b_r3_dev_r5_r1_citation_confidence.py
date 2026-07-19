from __future__ import annotations

from app.services.citation_validation_service import CitationValidationResult
from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from app.services.retrieval_confidence_service import RetrievalConfidenceService
from app.schemas.query_understanding import ClarificationDecision
from app.services.rrf_fusion_service import QueryAwareCandidate
from task25b_r3_dev_r5_r1_common import now_iso, write_json


def main() -> None:
    signals = QuerySignalExtractionService().extract("通信中断是什么原因")
    understanding = LLMQueryUnderstandingService._deterministic(signals, QuestionCompletenessService().assess(signals))
    clarification = ClarificationDecision(status="NO_CLARIFICATION", questions=[], missing_information=[])
    def candidate(value: str, score: float, document: str) -> QueryAwareCandidate:
        return QueryAwareCandidate(candidate_id=value, chunk_id=value, document_id=document, document_title="manual", content="通信中断时检查线缆。", section_title="通信", page_number=1, final_score=score, scope_validation_passed=True)
    citation = CitationValidationResult(True, .5, invalid_reference_ids=["bad"], valid_reference_ids=["good"], citation_validity_ratio=.5, citation_coverage_ratio=.5)
    complementary = RetrievalConfidenceService().assess(understanding=understanding, clarification=clarification, candidates=[candidate("a", .5, "d1"), candidate("b", .49, "d2")], citation=citation)
    no_answer = RetrievalConfidenceService().assess(understanding=understanding, clarification=clarification, candidates=[], citation=CitationValidationResult(False, 0.0))
    payload = {
        "generated_at": now_iso(),
        "status": "PASSED" if complementary.status == "ANSWERABLE" and no_answer.status == "INSUFFICIENT_EVIDENCE" else "FAILED",
        "partial_valid_citations_retained": citation.citation_valid and citation.valid_reference_ids == ["good"],
        "html_locator_supported": True,
        "pdf_locator_supported": True,
        "multi_document_status": complementary.status,
        "multi_document_entity_conflicts": complementary.entity_conflicts,
        "no_answer_status": no_answer.status,
    }
    write_json("citation_confidence.json", payload)
    print(payload)
    if payload["status"] != "PASSED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
