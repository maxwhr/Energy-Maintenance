from app.services.retrieval_plan_service import IntentAnchorCoverageMatrix


def test_requested_anchor_sets_are_unioned_and_full_section_is_last():
    anchors = IntentAnchorCoverageMatrix.resolve("TROUBLESHOOTING", ["CAUSE", "ACTION", "VERIFICATION"])
    assert {"SYMPTOM", "CAUSE", "ACTION", "PROCEDURE", "SAFETY", "VERIFICATION"} <= set(anchors)
    assert anchors[-1] == "FULL_SECTION"
