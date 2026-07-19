from app.services.semantic_unit_retrieval_service import SemanticUnitRetrievalService


def test_intent_routes_to_at_most_three_relevant_anchor_types() -> None:
    intent, anchors = SemanticUnitRetrievalService.classify_intent("RS485通信离线后应该怎么处理？")
    assert intent == "communication"
    assert anchors == ["COMMUNICATION", "SYMPTOM", "ACTION"]
    assert len(anchors) <= 3


def test_prerequisite_and_verification_are_distinct() -> None:
    assert SemanticUnitRetrievalService.classify_intent("操作之前需要准备什么？")[0] == "prerequisite"
    assert SemanticUnitRetrievalService.classify_intent("如何确认检修已经完成？")[0] == "verification"

