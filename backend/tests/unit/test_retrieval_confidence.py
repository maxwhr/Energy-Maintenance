from app.services.citation_validation_service import CitationValidationResult
from app.services.grounded_answer_boundary_service import GroundedAnswerBoundaryService
from app.services.retrieval_confidence_service import RetrievalConfidenceResult, RetrievalConfidenceService
from app.services.rrf_fusion_service import QueryAwareCandidate
from tests.unit.test_clarification_policy import decision
from tests.unit.test_evidence_rerank import understanding


def candidate(value: str, score: float, document: str = "doc"):
    return QueryAwareCandidate(
        candidate_id=value, chunk_id=value, document_id=document, document_title="manual",
        content="通信中断时检查线缆连接。", section_title="通信", page_number=12,
        final_score=score, scope_validation_passed=True,
    )


def citation(valid: bool):
    return CitationValidationResult(
        citation_valid=valid, citation_coverage=1.0 if valid else 0.0,
        invalid_reference_ids=[], invalid_reference_reasons={},
    )


def test_no_candidate_is_insufficient_evidence() -> None:
    result = RetrievalConfidenceService().assess(
        understanding=understanding(), clarification=decision("通信中断是什么原因"),
        candidates=[], citation=citation(False),
    )
    assert result.status == "INSUFFICIENT_EVIDENCE"


def test_close_cross_document_candidates_are_complementary_without_real_conflict() -> None:
    result = RetrievalConfidenceService().assess(
        understanding=understanding(), clarification=decision("通信中断是什么原因"),
        candidates=[candidate("a", 0.50, "d1"), candidate("b", 0.495, "d2")], citation=citation(True),
    )
    assert result.status == "ANSWERABLE"
    assert not result.entity_conflicts


def test_grounded_boundary_never_invents_repair_instructions() -> None:
    u = understanding()
    c = decision("通信中断是什么原因")
    result = GroundedAnswerBoundaryService().build(
        understanding=u,
        clarification=c,
        confidence=RetrievalConfidenceResult("INSUFFICIENT_EVIDENCE", 0.0, ["none"]),
        candidates=[],
    )
    assert result["unsupported_repair_instructions"] == 0
    assert result["confirmed_evidence"] == []
    assert result["insufficient_evidence_notice"]


def test_explicit_alarm_without_exact_support_is_no_answer() -> None:
    u = understanding()
    u.alarm_codes = ["999999"]
    result = RetrievalConfidenceService().assess(
        understanding=u,
        clarification=decision("通信中断是什么原因"),
        candidates=[candidate("a", 0.5)],
        citation=citation(True),
    )
    assert result.status == "INSUFFICIENT_EVIDENCE"
    assert result.reason_codes == ["explicit_alarm_not_supported"]
