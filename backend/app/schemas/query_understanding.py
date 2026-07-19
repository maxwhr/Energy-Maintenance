from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


PrimaryIntent = Literal[
    "DIAGNOSIS", "CAUSE", "TROUBLESHOOTING", "PROCEDURE", "SAFETY", "ALARM",
    "COMPONENT", "PREREQUISITE", "VERIFICATION", "COMMUNICATION", "GENERAL",
]
CompletenessStatus = Literal["CLEAR", "PARTIALLY_SPECIFIED", "AMBIGUOUS", "INSUFFICIENT_INFORMATION"]
ClarificationStatus = Literal["NO_CLARIFICATION", "CLARIFICATION_RECOMMENDED", "CLARIFICATION_REQUIRED"]
QueryUnderstandingMode = Literal[
    "FAST_PATH",
    "DETERMINISTIC",
    "DETERMINISTIC_WITH_CLARIFICATION",
    "MINIMAX_AMBIGUITY_RESOLUTION",
    "SAFE_FALLBACK",
    # Historical R5-R3-MM values remain readable; R5-R4-MM never emits them.
    "DETERMINISTIC_NORMALIZATION",
    "MINIMAX_TOOL",
]
QueryUnderstandingV2Intent = Literal[
    "CAUSE", "TROUBLESHOOTING", "PROCEDURE", "SAFETY", "ALARM",
    "PREREQUISITE", "VERIFICATION", "COMMUNICATION", "GENERAL",
]
RequestedInformationV2 = Literal[
    "CAUSE", "ACTION", "PROCEDURE", "SAFETY", "ALARM_MEANING",
    "PREREQUISITE", "VERIFICATION", "CONFIGURATION", "GENERAL_INFORMATION",
]
QueryAmbiguityV2 = Literal["CLEAR", "PARTIAL", "AMBIGUOUS", "INSUFFICIENT"]
MissingSlotV2 = Literal[
    "DEVICE_MODEL", "ALARM_CODE", "SPECIFIC_SYMPTOM", "COMPONENT",
    "COMMUNICATION_METHOD", "OCCURRENCE_CONDITION", "REQUESTED_ACTION",
]


class QuerySignals(BaseModel):
    original_query: str
    normalized_query: str
    manufacturer: str | None = None
    product_family: str | None = None
    model: str | None = None
    model_original: str | None = None
    model_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    alarm_code: str | None = None
    fault_type: str | None = None
    maintenance_intent: str | None = None
    safety_risk: str | None = None
    device_models: list[str] = Field(default_factory=list)
    alarm_codes: list[str] = Field(default_factory=list)
    alarm_names: list[str] = Field(default_factory=list)
    fault_codes: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    time_conditions: list[str] = Field(default_factory=list)
    operating_states: list[str] = Field(default_factory=list)
    numbers: list[str] = Field(default_factory=list)
    negative_expressions: list[str] = Field(default_factory=list)
    action_intent: list[str] = Field(default_factory=list)
    safety_intent: list[str] = Field(default_factory=list)
    communication_terms: list[str] = Field(default_factory=list)
    symptoms: list[str] = Field(default_factory=list)
    requested_information: list[str] = Field(default_factory=list)


class CompletenessAssessment(BaseModel):
    status: CompletenessStatus
    missing_information: list[str] = Field(default_factory=list)
    ambiguity: bool = False
    ambiguity_options: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)


class QueryUnderstandingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    original_query: str
    normalized_query: str
    canonical_question: str
    primary_intent: PrimaryIntent = "GENERAL"
    secondary_intents: list[PrimaryIntent] = Field(default_factory=list)
    confirmed_facts: dict[str, Any] = Field(default_factory=dict)
    normalized_semantics: dict[str, Any] = Field(default_factory=dict)
    device_models: list[str] = Field(default_factory=list)
    product_families: list[str] = Field(default_factory=list)
    equipment_categories: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    symptoms: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    alarm_codes: list[str] = Field(default_factory=list)
    alarm_names: list[str] = Field(default_factory=list)
    requested_information: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    ambiguity: bool = False
    ambiguity_options: list[str] = Field(default_factory=list)
    retrieval_hypotheses: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_queries: list[str] = Field(default_factory=list)
    route_hints: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarifying_question: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    model_provider: str = "deterministic"
    model_name: str = "query_understanding_rules_v1"
    prompt_version: str = "task25b_r3_dev_r5_query_understanding_v1"
    fallback_used: bool = False
    validation_errors: list[str] = Field(default_factory=list)
    completeness_status: CompletenessStatus = "PARTIALLY_SPECIFIED"
    fast_path: bool = False
    query_understanding_used: bool = False
    structured_model_diagnostics: dict[str, Any] = Field(default_factory=dict)
    query_understanding_mode: QueryUnderstandingMode = "DETERMINISTIC"
    requested_provider: str = "deterministic"
    actual_provider: str = "deterministic"
    provider_fallback: bool = False
    provider_fallback_reason: str | None = None
    circuit_breaker_state: str = "CLOSED"

    @field_validator(
        "device_models", "product_families", "equipment_categories", "components", "symptoms", "conditions",
        "alarm_codes", "alarm_names", "requested_information", "missing_information", "ambiguity_options",
        "retrieval_queries", "route_hints", "validation_errors", mode="before",
    )
    @classmethod
    def normalize_lists(cls, value):
        if value is None:
            return []
        return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


class RetrievalHypothesisPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    reason_code: str = Field(min_length=1, max_length=80)


class RetrievalQueryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_type: Literal["ORIGINAL", "SYMPTOM", "CAUSE", "ACTION", "SAFETY", "COMPONENT", "CONDITION", "GENERAL"]
    query_text: str = Field(min_length=1, max_length=500)
    weight: float = Field(ge=0.1, le=1.0)
    target_anchor_types: list[str] = Field(max_length=5)


class LLMQueryUnderstandingPatch(BaseModel):
    """Strict, bounded model output; deterministic signals remain authoritative."""

    model_config = ConfigDict(extra="forbid")

    canonical_question: str = Field(min_length=1, max_length=2000)
    primary_intent: PrimaryIntent
    secondary_intents: list[PrimaryIntent] = Field(max_length=5)
    normalized_symptoms: list[str] = Field(max_length=12)
    normalized_components: list[str] = Field(max_length=12)
    normalized_conditions: list[str] = Field(max_length=12)
    requested_information: list[str] = Field(max_length=5)
    missing_information: list[str] = Field(max_length=5)
    ambiguity: bool
    ambiguity_options: list[str] = Field(max_length=5)
    retrieval_hypotheses: list[RetrievalHypothesisPatch] = Field(max_length=4)
    retrieval_queries: list[RetrievalQueryPatch] = Field(max_length=5)
    needs_clarification: bool
    clarifying_question: str | None = Field(max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("retrieval_queries", mode="before")
    @classmethod
    def normalize_legacy_retrieval_queries(cls, value):
        if isinstance(value, list):
            return [
                {
                    "query_type": "GENERAL",
                    "query_text": item,
                    "weight": 0.7,
                    "target_anchor_types": [],
                }
                if isinstance(item, str) else item
                for item in value
            ]
        return value


class QueryUnderstandingV2Patch(BaseModel):
    """Minimal model-owned contract; entities and retrieval planning stay deterministic."""

    model_config = ConfigDict(extra="forbid")

    intent: QueryUnderstandingV2Intent = Field(
        description="用户首要请求；问原因选CAUSE，问排查选TROUBLESHOOTING，问通信但未明确原因/动作才选COMMUNICATION。"
    )
    canonical_query: str = Field(
        min_length=1, max_length=256, description="仅标准化用户原意，不新增型号、告警、原因、步骤或事实。"
    )
    requested_information: list[RequestedInformationV2] = Field(
        min_length=1, max_length=5, description="用户明确希望检索的信息类型。"
    )
    ambiguity: QueryAmbiguityV2 = Field(description="问题清晰度。")
    missing_slots: list[MissingSlotV2] = Field(max_length=4, description="检索所缺的关键信息。")
    needs_clarification: bool = Field(description="缺少信息导致无法可靠检索时为true。")
    clarifying_question: str = Field(
        max_length=160, description="需要追问时给一个短问题，否则必须为空字符串。"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="查询理解置信度。")


class DeterministicUnderstanding(BaseModel):
    """Rule-owned query understanding used by the production R5-R4-MM path."""

    model_config = ConfigDict(extra="forbid")

    intent: QueryUnderstandingV2Intent
    canonical_query: str = Field(min_length=1, max_length=512)
    requested_information: list[RequestedInformationV2] = Field(default_factory=list, max_length=5)
    confirmed_facts: dict[str, Any] = Field(default_factory=dict)
    normalized_symptoms: list[str] = Field(default_factory=list, max_length=12)
    normalized_components: list[str] = Field(default_factory=list, max_length=12)
    normalized_conditions: list[str] = Field(default_factory=list, max_length=12)
    ambiguity: QueryAmbiguityV2 = "CLEAR"
    missing_slots: list[MissingSlotV2] = Field(default_factory=list, max_length=4)
    needs_clarification: bool = False
    confidence: float = Field(ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list, max_length=12)


class AmbiguityInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interpretation_id: Literal["i0", "i1", "i2", "i3"]
    intent: QueryUnderstandingV2Intent
    canonical_query: str = Field(min_length=1, max_length=256)
    required_slots: list[MissingSlotV2] = Field(default_factory=list, max_length=4)
    supporting_signals: list[str] = Field(default_factory=list, max_length=8)
    confidence: float = Field(ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list, max_length=8)


class MiniMaxAmbiguityPatch(BaseModel):
    """The only fields MiniMax may own during ambiguity resolution."""

    model_config = ConfigDict(extra="forbid")

    selected_interpretation_ids: list[Literal["i0", "i1", "i2", "i3"]] = Field(
        default_factory=list, max_length=2
    )
    needs_clarification: bool
    missing_slots: list[MissingSlotV2] = Field(default_factory=list, max_length=4)
    confidence: float = Field(ge=0.0, le=1.0)


class ClarificationDecision(BaseModel):
    status: ClarificationStatus
    questions: list[str] = Field(default_factory=list, max_length=3)
    missing_information: list[str] = Field(default_factory=list)
    suppress_repair_instructions: bool = False
    reason_codes: list[str] = Field(default_factory=list)


class ClarificationRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=128)
    clarification: str = Field(min_length=1, max_length=2000)
    enable_llm: bool = True


class UnderstandQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    enable_llm: bool = True

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        return value.strip()
