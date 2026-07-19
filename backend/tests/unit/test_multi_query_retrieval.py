from app.schemas.retrieval_scope import RetrievalScope
from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.multi_query_retrieval_service import MultiQueryRetrievalService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from app.services.retrieval_plan_service import RetrievalPlanService
from app.services.clarification_policy_service import ClarificationPolicyService
from app.services.rrf_fusion_service import QueryAwareCandidate


def test_multi_query_executes_requested_jobs_without_expanding_scope(monkeypatch) -> None:
    monkeypatch.setenv("TASK25B_ALLOW_REAL_API", "false")
    signals = QuerySignalExtractionService().extract("通信中断是什么原因")
    assessment = QuestionCompletenessService().assess(signals)
    understanding = LLMQueryUnderstandingService._deterministic(signals, assessment)
    clarification = ClarificationPolicyService().decide(
        signals=signals, assessment=assessment, understanding=understanding
    )
    plan = RetrievalPlanService().build(understanding, clarification=clarification)
    scope = RetrievalScope(
        scope_id="chinese_engineering_pilot_r2",
        corpus_type="engineering_pilot",
        normalized_language="zh-CN",
        allowed_document_ids=(),
        required_document_status="active",
        required_chunk_status="active",
        required_approval_mode=("engineering_approved_for_pilot",),
        approved_for_pilot=True,
        current_version_only=True,
        collection_name="energy_kn_te_v4_1024_v1",
        partition_name="pilot_r2",
    )

    def fetch(channel: str, query: str, query_type: str):
        return [QueryAwareCandidate(
            candidate_id=f"{channel}:{query}", chunk_id=f"{channel}:{query}", document_id="doc",
            document_title="manual", content="evidence", source_channels={channel},
            source_query_types={query_type}, scope_validation_passed=True,
        )]

    result = MultiQueryRetrievalService(allow_real_api=False, channel_fetcher=fetch).retrieve(
        plan=plan, understanding=understanding, scope=scope
    )
    assert result.diagnostics["jobs"] == sum(len(values) for values in plan.channel_queries.values())
    assert result.diagnostics["scope_expanded"] is False
    assert set(result.actual_channels) == set(plan.requested_channels)
