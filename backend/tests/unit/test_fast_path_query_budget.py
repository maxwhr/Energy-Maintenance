from __future__ import annotations

from unittest.mock import patch

from app.schemas.query_understanding import ClarificationDecision, QueryUnderstandingResult
from app.schemas.retrieval_plan import RetrievalQueryVariant
from app.services.retrieval_plan_service import RetrievalPlanService


def test_fast_path_limits_scoped_keyword_variants_to_two() -> None:
    understanding = QueryUnderstandingResult(
        request_id="fast-path-test",
        original_query="SUN2000 Error 225 safety inspection",
        normalized_query="SUN2000 Error 225 safety inspection",
        canonical_question="SUN2000 Error 225 safety inspection",
        primary_intent="TROUBLESHOOTING",
        fast_path=True,
    )
    variants = [
        RetrievalQueryVariant(variant_type="ORIGINAL", query="variant one"),
        RetrievalQueryVariant(variant_type="CANONICAL", query="variant two"),
        RetrievalQueryVariant(variant_type="REQUEST_QUERY", query="variant three"),
    ]
    clarification = ClarificationDecision(status="NO_CLARIFICATION")

    with patch(
        "app.services.retrieval_plan_service.DeterministicQueryExpansionService.expand",
        return_value=variants,
    ):
        plan = RetrievalPlanService().build(understanding, clarification=clarification)

    assert plan.channel_queries["SCOPED_KEYWORD"] == ["variant one", "variant two"]


def test_deep_path_preserves_all_scoped_keyword_variants() -> None:
    understanding = QueryUnderstandingResult(
        request_id="deep-path-test",
        original_query="SUN2000 troubleshooting evidence",
        normalized_query="SUN2000 troubleshooting evidence",
        canonical_question="SUN2000 troubleshooting evidence",
        primary_intent="TROUBLESHOOTING",
        fast_path=False,
    )
    variants = [
        RetrievalQueryVariant(variant_type="ORIGINAL", query="variant one"),
        RetrievalQueryVariant(variant_type="CANONICAL", query="variant two"),
        RetrievalQueryVariant(variant_type="REQUEST_QUERY", query="variant three"),
    ]
    clarification = ClarificationDecision(status="NO_CLARIFICATION")

    with patch(
        "app.services.retrieval_plan_service.DeterministicQueryExpansionService.expand",
        return_value=variants,
    ):
        plan = RetrievalPlanService().build(understanding, clarification=clarification)

    assert plan.channel_queries["SCOPED_KEYWORD"] == [
        "variant one",
        "variant two",
        "variant three",
    ]
