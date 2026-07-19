from types import SimpleNamespace

from app.services.candidate_feature_context import CandidateFeatureContext


def test_computed_candidate_features_are_captured_for_downstream_reuse():
    item = SimpleNamespace(
        candidate_id="a", exact_model_match=True, exact_alarm_match=False,
        requested_information_support={"ACTION"}, requested_information_coverage=1.0,
        direct_answer_score=0.8, direct_answer_level="DIRECT", generality_penalty=0.0,
        source_channels={"SCOPED_KEYWORD"},
    )
    diagnostics = CandidateFeatureContext().capture([item])
    assert diagnostics["feature_calculations_reused"] == 1
    assert diagnostics["benchmark_relevance_used"] is False
