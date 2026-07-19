from app.schemas.retrieval_plan import RetrievalPlan, RetrievalQueryVariant
from app.services.query_variant_deduplication_service import QueryVariantDeduplicationService


def test_normalized_duplicate_is_removed_and_original_is_retained():
    plan = RetrievalPlan(
        original_query="通信中断",
        canonical_query="通信中断",
        query_variants=[
            RetrievalQueryVariant(variant_type="ORIGINAL", query="通信中断"),
            RetrievalQueryVariant(variant_type="CANONICAL", query=" 通信中断！"),
        ],
        requested_channels=["SCOPED_KEYWORD"],
        channel_queries={"SCOPED_KEYWORD": ["通信中断", " 通信中断！"]},
    )
    result = QueryVariantDeduplicationService().deduplicate(plan)
    assert [item.variant_type for item in result.plan.query_variants] == ["ORIGINAL"]
    assert result.diagnostics["variants_removed"] == 1
    assert result.diagnostics["case_id_used"] is False
