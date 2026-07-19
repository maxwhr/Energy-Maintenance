from app.services.deterministic_evidence_rerank_service import DeterministicEvidenceRerankService


def test_complete_specific_answer_scores_above_background():
    direct = DeterministicEvidenceRerankService.direct_answer_score(
        coverage=1, intent_match=1, entity_match=1, specificity=1, citation_quality=1
    )
    background = DeterministicEvidenceRerankService.direct_answer_score(
        coverage=0, intent_match=.2, entity_match=1, specificity=.2, citation_quality=1
    )
    assert direct > background
    assert DeterministicEvidenceRerankService.direct_answer_level(direct, 1, 0) == "DIRECT_ANSWER"
