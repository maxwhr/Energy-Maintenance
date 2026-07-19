from __future__ import annotations

from app.services.clarification_policy_service import ClarificationPolicyService
from app.services.deterministic_query_understanding_service import DeterministicQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from app.services.retrieval_plan_service import RetrievalPlanService


def understand(query: str):
    signals = QuerySignalExtractionService().extract(query)
    assessment = QuestionCompletenessService().assess(signals)
    deterministic = DeterministicQueryUnderstandingService().understand(signals=signals, assessment=assessment)
    return DeterministicQueryUnderstandingService().to_result(
        deterministic=deterministic, signals=signals, assessment=assessment
    )


def plan(query: str):
    signals = QuerySignalExtractionService().extract(query)
    assessment = QuestionCompletenessService().assess(signals)
    understanding = understand(query)
    clarification = ClarificationPolicyService().decide(
        signals=signals, assessment=assessment, understanding=understanding
    )
    return RetrievalPlanService().build(understanding, clarification=clarification)
