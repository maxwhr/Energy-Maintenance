import json

from app.services.evidence_aware_rerank_service import EvidenceAwareRerankService
from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from app.services.rrf_fusion_service import QueryAwareCandidate


def understanding():
    signals = QuerySignalExtractionService().extract("通信中断是什么原因")
    assessment = QuestionCompletenessService().assess(signals)
    return LLMQueryUnderstandingService._deterministic(signals, assessment)


def candidates():
    return [QueryAwareCandidate(
        candidate_id=value, chunk_id=value, document_id=f"doc-{value}", document_title="manual",
        content="通信中断可能由线缆松动导致", source_channels={"SCOPED_KEYWORD"},
        source_query_types={"ORIGINAL"}, rrf_score=0.02 - index * 0.001,
        final_score=0.02 - index * 0.001, scope_validation_passed=True,
    ) for index, value in enumerate(("a", "b", "c"))]


def test_rerank_cannot_add_candidate() -> None:
    service = EvidenceAwareRerankService(None, model_call=lambda _: json.dumps([
        {"candidate_id": "not-supplied", "final_rerank_score": 1.0}
    ]))
    result = service.rerank(candidates(), understanding=understanding(), allow_real_api=True)
    assert result.fallback is True
    assert {item.candidate_id for item in result.candidates} == {"a", "b", "c"}
    assert result.candidate_additions == 0
    assert result.candidate_source_modifications == 0


def test_exact_fast_path_skips_rerank() -> None:
    signals = QuerySignalExtractionService().extract("SUN2000-100KTL-M1 通信参数")
    u = LLMQueryUnderstandingService._deterministic(signals, QuestionCompletenessService().assess(signals))
    result = EvidenceAwareRerankService(None).rerank(candidates(), understanding=u, allow_real_api=False)
    assert result.used is False
    assert result.eligible is False
