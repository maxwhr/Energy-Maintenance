from app.services.deterministic_evidence_rerank_service import DeterministicEvidenceRerankService
from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.minimax_resilience import MiniMaxCircuitBreaker
from app.services.minimax_tiebreak_service import MiniMaxTieBreakService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from tests.minimax_test_helpers import FakeStructuredService, candidate, minimax_settings, query_patch


def test_query_understanding_deterministic_rerank_and_optional_tiebreak_compose() -> None:
    settings = minimax_settings()
    signals = QuerySignalExtractionService().extract("通信老是掉线，啥原因")
    qu = LLMQueryUnderstandingService(
        None, settings=settings, structured_service=FakeStructuredService(query_patch()),
        circuit_breaker=MiniMaxCircuitBreaker(),
    ).understand(
        signals=signals, assessment=QuestionCompletenessService().assess(signals),
        enable_llm=True, allow_real_api=True,
    )
    candidates = [
        candidate("a", content="通信原因和检查", rrf=0.5),
        candidate("b", content="通信处理步骤", rrf=0.49),
    ]
    deterministic = DeterministicEvidenceRerankService(settings).rerank(candidates, understanding=qu)
    tie = MiniMaxTieBreakService(
        settings=settings,
        structured_service=FakeStructuredService({
            "ordered_candidate_ids": ["c0", "c1"],
            "scores": [
                {"candidate_id": "c0", "support": 0.9, "intent_match": 0.9, "contradiction": False},
                {"candidate_id": "c1", "support": 0.8, "intent_match": 0.8, "contradiction": False},
            ],
            "needs_clarification": False,
        }),
        circuit_breaker=MiniMaxCircuitBreaker(),
    ).rerank(deterministic.candidates, understanding=qu, allow_real_api=True, force=True)
    assert qu.actual_provider.startswith("minimax")
    assert len(tie.candidates) == len(candidates)
    assert tie.diagnostics["structured_success"] is True
