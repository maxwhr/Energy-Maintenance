from app.services.retrieval_plan_service import IntentAnchorCoverageMatrix


def test_multi_intent_matrix_does_not_collapse_to_primary_anchor_only():
    anchors = IntentAnchorCoverageMatrix.resolve("PROCEDURE", ["PREREQUISITE", "SAFETY", "VERIFICATION"])
    assert {"PROCEDURE", "PREREQUISITE", "SAFETY", "VERIFICATION", "ACTION"} <= set(anchors)
    assert len(anchors) > 4
