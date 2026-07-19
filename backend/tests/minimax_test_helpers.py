from __future__ import annotations

from uuid import uuid4

from app.core.config import Settings
from app.schemas.structured_model import StructuredModelResult
from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from app.services.rrf_fusion_service import QueryAwareCandidate


def minimax_settings(**updates) -> Settings:
    base = {
        "MINIMAX_ENABLED": True,
        "MINIMAX_API_KEY": "unit-test-token",
        "MINIMAX_PROTOCOL": "anthropic",
        "MINIMAX_MODEL": "MiniMax-M3",
        "MINIMAX_QUERY_UNDERSTANDING_MODEL": "MiniMax-M3",
        "MINIMAX_TIEBREAK_MODEL": "MiniMax-M3",
        "MINIMAX_THINKING_TYPE": "disabled",
        "MINIMAX_TOOL_CALL_ENABLED": True,
        "MINIMAX_FORCE_TOOL_CHOICE": True,
        "MINIMAX_SERVICE_TIER": "standard",
        "MINIMAX_MAX_RETRIES": 0,
        "TASK25B_ALLOW_REAL_API": True,
        "RAG_QUERY_UNDERSTANDING_PROVIDER": "minimax",
        "RAG_QUERY_UNDERSTANDING_RUNTIME_MODEL": "MiniMax-M3",
        "RAG_TIEBREAK_PROVIDER": "minimax",
        "RAG_REQUEST_LEVEL_PROVIDER_FALLBACK_ENABLED": False,
    }
    base.update(updates)
    return Settings(_env_file=None).model_copy(update=base)


def query_patch() -> dict:
    return {
        "intent": "COMMUNICATION",
        "canonical_query": "设备通信频繁掉线，查询可能原因和排查方法",
        "requested_information": ["CAUSE", "ACTION"],
        "ambiguity": "PARTIAL",
        "missing_slots": ["DEVICE_MODEL"],
        "needs_clarification": False,
        "clarifying_question": "",
        "confidence": 0.86,
    }


class FakeStructuredService:
    def __init__(self, payload: dict | None = None, *, success: bool = True, error_code: str | None = None):
        self.payload = payload
        self.success = success
        self.error_code = error_code
        self.requests = []

    def call(self, request, response_model):
        self.requests.append(request)
        parsed = response_model.model_validate(self.payload).model_dump(mode="json") if self.success and self.payload is not None else None
        return StructuredModelResult(
            success=self.success,
            parsed_payload=parsed,
            response_format_mode="MINIMAX_ANTHROPIC_TOOL",
            structured_mode="MINIMAX_ANTHROPIC_TOOL",
            provider="minimax_anthropic",
            model="MiniMax-M3",
            protocol="anthropic",
            parse_strategy="TOOL_INPUT" if self.success else "FAILED",
            provider_status="success" if self.success else "failed",
            provider_error_code=self.error_code,
            fallback_reason=None if self.success else "structured_output_exhausted",
            attempt_count=1,
            latency_ms=12.0,
            trace_id="test-trace",
            tool_name=request.tool_name,
            tool_call_count=1 if self.success else 0,
            tool_input_valid=self.success,
        )


def understanding(query: str = "通信老是掉线，啥原因"):
    signals = QuerySignalExtractionService().extract(query)
    assessment = QuestionCompletenessService().assess(signals)
    return LLMQueryUnderstandingService._deterministic(signals, assessment)


def candidate(
    label: str,
    *,
    content: str,
    rrf: float,
    exact_model: bool = False,
    exact_alarm: bool = False,
    channel: str = "SCOPED_KEYWORD",
) -> QueryAwareCandidate:
    chunk_id = str(uuid4())
    return QueryAwareCandidate(
        candidate_id=label,
        chunk_id=chunk_id,
        document_id=str(uuid4()),
        document_title=f"官方文档 {label}",
        content=content,
        section_title="故障处理",
        page_number=2,
        source_channels={channel},
        source_query_types={"ORIGINAL"},
        raw_scores={channel: rrf},
        rrf_score=rrf,
        final_score=rrf,
        exact_model_match=exact_model,
        exact_alarm_match=exact_alarm,
        source_chunk_ids=[chunk_id],
        source_locator={"page_number": 2, "section": "故障处理"},
        scope_validation_passed=True,
    )
