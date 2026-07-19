from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import User
from app.schemas.model_gateway import ModelMessage
from app.schemas.query_understanding import QueryUnderstandingResult
from app.schemas.structured_model import StructuredModelRequest
from app.services.rrf_fusion_service import QueryAwareCandidate
from app.services.structured_model_call_service import StructuredModelCallService


class RerankCandidateScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1, max_length=160)
    support_score: float = Field(ge=0.0, le=1.0)
    intent_match_score: float = Field(ge=0.0, le=1.0)
    device_match_score: float = Field(ge=0.0, le=1.0)
    alarm_match_score: float = Field(ge=0.0, le=1.0)
    symptom_match_score: float = Field(ge=0.0, le=1.0)
    condition_match_score: float = Field(ge=0.0, le=1.0)
    action_match_score: float = Field(ge=0.0, le=1.0)
    safety_match_score: float = Field(ge=0.0, le=1.0)
    contradiction: bool = False
    insufficient_context: bool = False
    final_score: float = Field(
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices("final_score", "final_rerank_score"),
    )
    reason_codes: list[str] = Field(default_factory=list, max_length=8)


class RerankStructuredPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rankings: list[RerankCandidateScore] = Field(min_length=1, max_length=12)


@dataclass(slots=True)
class EvidenceRerankResult:
    candidates: list[QueryAwareCandidate]
    used: bool
    fallback: bool
    eligible: bool
    candidate_additions: int
    candidate_source_modifications: int
    diagnostics: dict


class EvidenceAwareRerankService:
    def __init__(
        self,
        db: Session | None,
        *,
        current_user: User | None = None,
        model_call: Callable[[str], str] | None = None,
        structured_service: StructuredModelCallService | None = None,
    ) -> None:
        self.db = db
        self.current_user = current_user
        self.model_call = model_call
        self.settings = get_settings()
        transport = None
        if model_call is not None:
            def transport(request, _mode):
                raw = model_call(request.messages[-1].content)
                stripped = (raw or "").strip()
                return json.dumps({"rankings": json.loads(stripped)}, ensure_ascii=False) if stripped.startswith("[") else raw
        self.structured = structured_service or StructuredModelCallService(model_call=transport)

    def rerank(
        self,
        candidates: list[QueryAwareCandidate],
        *,
        understanding: QueryUnderstandingResult,
        allow_real_api: bool,
        force: bool = False,
    ) -> EvidenceRerankResult:
        original = list(candidates)
        original_ids = [item.candidate_id for item in original]
        eligible = bool(original) and (force or self._eligible(original, understanding))
        base_diagnostics = {
            "rerank_requested": eligible,
            "rerank_model_called": False,
            "rerank_structured_success": False,
            "rerank_parse_strategy": None,
            "rerank_fallback_stage": None,
            "rerank_fallback_reason": None,
            "rerank_trace_id": None,
            "candidate_count_in": len(original),
            "candidate_count_out": len(original),
            "candidate_additions": 0,
            "candidate_removals": 0,
            "order_changed": False,
        }
        if not eligible:
            return EvidenceRerankResult(original, False, False, False, 0, 0, {
                **base_diagnostics, "reason": "fast_path_or_not_needed",
            })
        if self.model_call is None and not (
            allow_real_api and self.settings.TASK25B_ALLOW_REAL_API and self.db and self.current_user
        ):
            return EvidenceRerankResult(original, True, True, True, 0, 0, {
                **base_diagnostics,
                "rerank_fallback_stage": "pre_call_guard",
                "rerank_fallback_reason": "llm_not_allowed",
                "reason": "llm_not_allowed",
            })

        shortlist = original[:12]
        request = StructuredModelRequest(
            purpose="evidence_rerank",
            messages=[
                ModelMessage(
                    role="system",
                    content=(
                        "Output the JSON object immediately. Use at most 80 internal reasoning tokens. "
                        "Score only supplied candidate IDs. Do not add candidates, facts, repair instructions, or prose."
                    ),
                ),
                ModelMessage(role="user", content=self._prompt(shortlist, understanding)),
            ],
            response_schema=RerankStructuredPayload.model_json_schema(),
            schema_name="evidence_rerank_r5_r1",
            temperature=0.0,
            max_tokens=1800,
            timeout_seconds=max(20.0, self.settings.RERANK_TIMEOUT_SECONDS),
            allow_retry=False,
            provider="cloud_openai",
            model=self.settings.CLOUD_LLM_MODEL,
            trace_context={"candidate_count": len(shortlist), "preferred_mode": "JSON_OBJECT"},
            reasoning_effort="low",
        )
        structured = self.structured.call(request, RerankStructuredPayload)
        diagnostics = {
            **base_diagnostics,
            "rerank_model_called": True,
            "rerank_structured_success": structured.success,
            "rerank_parse_strategy": structured.parse_strategy,
            "rerank_fallback_stage": None if structured.success else "structured_model_call",
            "rerank_fallback_reason": structured.fallback_reason,
            "rerank_trace_id": structured.trace_id,
            "response_format_mode": structured.response_format_mode,
            "provider_status": structured.provider_status,
            "provider_error_code": structured.provider_error_code,
            "validation_errors": structured.validation_errors,
            "latency_ms": structured.latency_ms,
            "raw_text_length": structured.raw_text_length,
            "raw_top_level_type": structured.raw_top_level_type,
            "raw_shape": structured.raw_shape,
            "response_field_names": structured.response_field_names,
            "provider_response_meta": structured.provider_response_meta,
        }
        if not structured.success or structured.parsed_payload is None:
            return EvidenceRerankResult(original, True, True, True, 0, 0, diagnostics)

        payload = RerankStructuredPayload.model_validate(structured.parsed_payload)
        allowed = {item.candidate_id: item for item in shortlist}
        score_rows: dict[str, RerankCandidateScore] = {}
        for row in payload.rankings:
            if row.candidate_id not in allowed:
                diagnostics.update({
                    "rerank_structured_success": False,
                    "rerank_fallback_stage": "candidate_boundary_validation",
                    "rerank_fallback_reason": "candidate_addition_attempted",
                    "candidate_additions": 1,
                })
                return EvidenceRerankResult(original, True, True, True, 1, 0, diagnostics)
            if row.candidate_id in score_rows:
                diagnostics.update({
                    "rerank_structured_success": False,
                    "rerank_fallback_stage": "candidate_boundary_validation",
                    "rerank_fallback_reason": "duplicate_candidate_score",
                })
                return EvidenceRerankResult(original, True, True, True, 0, 0, diagnostics)
            score_rows[row.candidate_id] = row

        original_positions = {candidate_id: index for index, candidate_id in enumerate(original_ids)}
        for item in shortlist:
            row = score_rows.get(item.candidate_id)
            if row is None:
                item.rerank_score = None
                item.final_score = item.rrf_score
                continue
            item.rerank_score = row.final_score
            item.final_score = round(0.35 * item.rrf_score + 0.65 * row.final_score, 8)
        ranked_shortlist = sorted(
            shortlist,
            key=lambda item: (-item.final_score, original_positions[item.candidate_id]),
        )
        ranked = ranked_shortlist + original[12:]
        ranked_ids = [item.candidate_id for item in ranked]
        if set(ranked_ids) != set(original_ids) or len(ranked_ids) != len(original_ids):
            diagnostics.update({
                "rerank_structured_success": False,
                "rerank_fallback_stage": "candidate_boundary_validation",
                "rerank_fallback_reason": "candidate_set_changed",
            })
            return EvidenceRerankResult(original, True, True, True, 0, 0, diagnostics)
        diagnostics.update({
            "candidate_count_out": len(ranked),
            "order_changed": ranked_ids != original_ids,
            "scored_candidates": len(score_rows),
        })
        return EvidenceRerankResult(ranked, True, False, True, 0, 0, diagnostics)

    @staticmethod
    def _eligible(candidates: list[QueryAwareCandidate], understanding: QueryUnderstandingResult) -> bool:
        if understanding.fast_path or len(candidates) < 2:
            return False
        top = max(candidates[0].rrf_score, 1e-9)
        normalized_margin = (candidates[0].rrf_score - candidates[1].rrf_score) / top
        evidence_ambiguous = normalized_margin < 0.18
        return evidence_ambiguous and understanding.primary_intent in {
            "DIAGNOSIS", "CAUSE", "TROUBLESHOOTING", "SAFETY", "COMMUNICATION", "ALARM",
        }

    @staticmethod
    def _prompt(candidates: list[QueryAwareCandidate], understanding: QueryUnderstandingResult) -> str:
        payload = {
            "query": understanding.canonical_question,
            "confirmed_facts": understanding.confirmed_facts,
            "normalized_semantics": understanding.normalized_semantics,
            "primary_intent": understanding.primary_intent,
            "candidates": [{
                "candidate_id": item.candidate_id,
                "title": item.document_title[:120],
                "section": (item.section_title or "")[:120],
                "evidence_excerpt": " ".join(item.content.split())[:240],
                "source_type": "SEMANTIC_UNIT" if item.semantic_unit_id else "CHUNK",
            } for item in candidates],
            "output_exact_shape": {
                "rankings": [{
                    "candidate_id": candidates[0].candidate_id,
                    "support_score": 0.5,
                    "intent_match_score": 0.5,
                    "device_match_score": 0.5,
                    "alarm_match_score": 0.5,
                    "symptom_match_score": 0.5,
                    "condition_match_score": 0.5,
                    "action_match_score": 0.5,
                    "safety_match_score": 0.5,
                    "contradiction": False,
                    "insufficient_context": False,
                    "final_score": 0.5,
                    "reason_codes": ["SUPPORTED"],
                }],
            },
            "rules": "Return only output_exact_shape JSON with one row for every supplied candidate ID; include supplied IDs only; scores 0..1; reason_codes only, no prose.",
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
