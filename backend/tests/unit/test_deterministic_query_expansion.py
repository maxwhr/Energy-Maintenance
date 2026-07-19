from app.services.deterministic_query_expansion_service import DeterministicQueryExpansionService
from tests.minimax_test_helpers import understanding


def test_deterministic_expansion_is_bounded_and_original_is_first() -> None:
    item = understanding("机器晚上总掉线，白天又好了，怎么查？")
    item.canonical_question = "设备夜间通信中断，白天恢复正常"
    item.primary_intent = "COMMUNICATION"
    item.requested_information = ["CAUSE", "ACTION"]
    variants = DeterministicQueryExpansionService().expand(item)
    assert variants[0].variant_type == "ORIGINAL"
    assert variants[0].query == item.original_query
    assert len(variants) <= 5
    assert all(value.variant_type in {
        "ORIGINAL", "CANONICAL", "SYMPTOM_QUERY", "REQUEST_QUERY", "CONDITION_QUERY"
    } for value in variants)
