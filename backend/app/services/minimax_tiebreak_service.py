from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings, get_settings
from app.schemas.model_gateway import ModelMessage
from app.schemas.query_understanding import QueryUnderstandingResult
from app.schemas.structured_model import StructuredModelRequest
from app.services.minimax_resilience import MiniMaxCircuitBreaker, TTLCache, get_minimax_circuit_breaker
from app.services.rrf_fusion_service import QueryAwareCandidate
from app.services.structured_model_call_service import StructuredModelCallService


CandidateAlias = Literal["c0", "c1", "c2", "c3", "c4", "c5"]


class CandidateTieBreakScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: CandidateAlias
    support: float = Field(ge=0.0, le=1.0)
    intent_match: float = Field(ge=0.0, le=1.0)
    contradiction: bool


class CandidateTieBreakPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ordered_candidate_ids: list[CandidateAlias] = Field(min_length=1, max_length=6)
    scores: list[CandidateTieBreakScore] = Field(min_length=1, max_length=6)
    needs_clarification: bool


@dataclass(slots=True)
class MiniMaxTieBreakResult:
    candidates: list[QueryAwareCandidate]
    diagnostics: dict[str, Any]


class MiniMaxTieBreakService:
    PROMPT_VERSION = "task25b_r3_dev_r5_r2_mm_tiebreak_v1"
    _cache: TTLCache[dict] | None = None

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        structured_service: StructuredModelCallService | None = None,
        circuit_breaker: MiniMaxCircuitBreaker | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.structured = structured_service or StructuredModelCallService(settings=self.settings)
        self.breaker = circuit_breaker or get_minimax_circuit_breaker(
            cooldown_seconds=self.settings.MINIMAX_CIRCUIT_COOLDOWN_SECONDS
        )
        if self.__class__._cache is None:
            self.__class__._cache = TTLCache(
                max_entries=self.settings.MINIMAX_CACHE_MAX_ENTRIES,
                ttl_seconds=self.settings.MINIMAX_CACHE_TTL_SECONDS,
            )

    def rerank(
        self,
        candidates: list[QueryAwareCandidate],
        *,
        understanding: QueryUnderstandingResult,
        allow_real_api: bool,
        citation_status: dict[str, bool] | None = None,
        remaining_budget_ms: float | None = None,
        force: bool = False,
        max_candidates: int = 4,
    ) -> MiniMaxTieBreakResult:
        original = list(candidates)
        original_ids = [item.candidate_id for item in original]
        eligible, skipped_reason = self._eligible(
            original,
            understanding=understanding,
            citation_status=citation_status,
            remaining_budget_ms=remaining_budget_ms,
            force=force,
        )
        base = {
            "eligible": eligible,
            "called": False,
            "skipped_reason": skipped_reason,
            "requested_provider": self.settings.RAG_TIEBREAK_PROVIDER,
            "actual_provider": "deterministic",
            "provider_fallback": False,
            "fallback_reason": None,
            "circuit_breaker_state": self.breaker.state("tiebreak"),
            "candidates_in": len(original),
            "candidates_out": len(original),
            "structured_success": False,
            "order_changed": False,
            "fallback_order_preserved": True,
            "candidate_additions": 0,
            "candidate_removals": 0,
            "source_modifications": 0,
            "cache_hit": False,
        }
        if not eligible:
            return MiniMaxTieBreakResult(original, base)
        requested_provider = self.settings.RAG_TIEBREAK_PROVIDER.strip().lower()
        configured = bool(
            requested_provider == "minimax"
            and self.settings.MINIMAX_ENABLED
            and self.settings.MINIMAX_API_KEY
            and self.settings.MINIMAX_PROTOCOL.strip().lower() == "anthropic"
            and self.settings.MINIMAX_TOOL_CALL_ENABLED
            and self.settings.MINIMAX_FORCE_TOOL_CHOICE
            and self.settings.MINIMAX_SERVICE_TIER.strip().lower() == "standard"
            and allow_real_api
            and self.settings.TASK25B_ALLOW_REAL_API
        )
        if not configured or not self.breaker.allow("tiebreak"):
            base.update({
                "skipped_reason": "CIRCUIT_OPEN" if self.breaker.state("tiebreak") == "OPEN" else "PROVIDER_UNAVAILABLE",
                "provider_fallback": True,
                "fallback_reason": "CIRCUIT_OPEN" if self.breaker.state("tiebreak") == "OPEN" else "PROVIDER_UNAVAILABLE",
                "circuit_breaker_state": self.breaker.state("tiebreak"),
            })
            return MiniMaxTieBreakResult(original, base)

        limit = min(max(2, int(max_candidates)), 6, self.settings.MINIMAX_MAX_TIEBREAK_CANDIDATES, len(original))
        shortlist = original[:limit]
        aliases = {f"c{index}": item for index, item in enumerate(shortlist)}
        cache_key = self.cache_key(understanding=understanding, shortlist=shortlist)
        assert self._cache is not None
        cached = self._cache.get(cache_key)
        if cached:
            return self._apply_order(original, aliases, cached["ordered_candidate_ids"], {
                **base,
                "called": False,
                "skipped_reason": None,
                "actual_provider": "minimax_cache",
                "structured_success": True,
                "cache_hit": True,
            })

        request = StructuredModelRequest(
            purpose="candidate_tiebreak",
            messages=[
                ModelMessage(
                    role="system",
                    content=(
                        "只比较给定候选对用户问题的直接证据支持度。不得新增、改写或删除候选、来源和引用。"
                        "必须调用 submit_candidate_tiebreak，不输出普通文本或思维过程。"
                    ),
                ),
                ModelMessage(role="user", content=self._prompt(understanding, aliases)),
            ],
            response_schema=CandidateTieBreakPatch.model_json_schema(),
            schema_name="candidate_tiebreak_r5_r2_mm",
            tool_name="submit_candidate_tiebreak",
            tool_description="提交给定候选别名的相对顺序和简化支持评分。",
            temperature=self.settings.MINIMAX_TEMPERATURE,
            top_p=self.settings.MINIMAX_TOP_P,
            service_tier=self.settings.MINIMAX_SERVICE_TIER,
            max_tokens=self.settings.MINIMAX_TIEBREAK_MAX_TOKENS,
            timeout_seconds=self.settings.MINIMAX_TIEBREAK_TIMEOUT_SECONDS,
            allow_retry=False,
            provider="minimax_anthropic",
            model=self.settings.MINIMAX_TIEBREAK_MODEL,
            trace_context={"candidate_count": len(shortlist)},
        )
        structured = self.structured.call(request, CandidateTieBreakPatch)
        base.update({
            "called": True,
            "skipped_reason": None,
            "actual_provider": "minimax",
            "structured_success": structured.success,
            "latency_ms": structured.latency_ms,
            "trace_id": structured.trace_id,
            "provider_status": structured.provider_status,
            "provider_error_code": structured.provider_error_code,
            "tool_call_used": structured.tool_call_count == 1,
        })
        if not structured.success or structured.parsed_payload is None:
            error_code = structured.provider_error_code or "SCHEMA_VALIDATION_FAILED"
            self.breaker.record(
                "tiebreak", success=False, error_code=error_code, latency_ms=structured.latency_ms
            )
            base.update({
                "provider_fallback": True,
                "fallback_reason": error_code,
                "circuit_breaker_state": self.breaker.state("tiebreak"),
            })
            return MiniMaxTieBreakResult(original, base)
        patch = CandidateTieBreakPatch.model_validate(structured.parsed_payload)
        boundary_error = self._validate_boundary(patch, set(aliases))
        if boundary_error:
            self.breaker.record(
                "tiebreak", success=False, error_code=boundary_error, latency_ms=structured.latency_ms
            )
            base.update({
                "structured_success": False,
                "provider_fallback": True,
                "fallback_reason": boundary_error,
                "circuit_breaker_state": self.breaker.state("tiebreak"),
            })
            return MiniMaxTieBreakResult(original, base)
        self.breaker.record("tiebreak", success=True, latency_ms=structured.latency_ms)
        ordered_aliases = list(patch.ordered_candidate_ids)
        ordered_aliases.extend(alias for alias in aliases if alias not in ordered_aliases)
        self._cache.set(cache_key, {"ordered_candidate_ids": ordered_aliases})
        base["circuit_breaker_state"] = self.breaker.state("tiebreak")
        return self._apply_order(original, aliases, ordered_aliases, base)

    def cache_key(
        self,
        *,
        understanding: QueryUnderstandingResult,
        shortlist: list[QueryAwareCandidate],
    ) -> str:
        understanding_hash = hashlib.sha256(
            json.dumps({
                "canonical_question": understanding.canonical_question,
                "primary_intent": understanding.primary_intent,
                "confirmed_facts": understanding.confirmed_facts,
                "normalized_semantics": understanding.normalized_semantics,
            }, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        candidate_set_hash = hashlib.sha256(
            "|".join(sorted(item.candidate_id for item in shortlist)).encode("utf-8")
        ).hexdigest()
        deterministic_order_hash = hashlib.sha256(
            "|".join(item.candidate_id for item in shortlist).encode("utf-8")
        ).hexdigest()
        payload = {
            "provider": "minimax",
            "model": self.settings.MINIMAX_TIEBREAK_MODEL,
            "prompt_version": self.PROMPT_VERSION,
            "query_understanding_hash": understanding_hash,
            "candidate_set_hash": candidate_set_hash,
            "deterministic_order_hash": deterministic_order_hash,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def _eligible(
        self,
        candidates: list[QueryAwareCandidate],
        *,
        understanding: QueryUnderstandingResult,
        citation_status: dict[str, bool] | None,
        remaining_budget_ms: float | None,
        force: bool,
    ) -> tuple[bool, str | None]:
        if not force and (
            not self.settings.RAG_OPTIONAL_LLM_TIEBREAK_ENABLED
            or not self.settings.RAG_TIEBREAK_EXPERIMENTAL_ENABLED
        ):
            return False, "DISABLED"
        if len(candidates) < 2:
            return False, "INSUFFICIENT_CANDIDATES"
        if self.breaker.state("tiebreak") == "OPEN":
            return False, "CIRCUIT_OPEN"
        if remaining_budget_ms is not None and remaining_budget_ms < self.settings.MINIMAX_TIEBREAK_TIMEOUT_SECONDS * 1000:
            return False, "LATENCY_BUDGET_INSUFFICIENT"
        if not force:
            if understanding.needs_clarification:
                return False, "CLARIFICATION_REQUIRED"
            if candidates[0].exact_model_match or candidates[0].exact_alarm_match:
                return False, "EXACT_ENTITY_PROTECTED"
            if citation_status is not None and sum(bool(citation_status.get(item.chunk_id)) for item in candidates[:4]) <= 1:
                return False, "ONLY_ONE_VALID_CITATION"
            top = max(abs(candidates[0].final_score), 1e-9)
            margin = (candidates[0].final_score - candidates[1].final_score) / top
            if margin >= self.settings.MINIMAX_TIEBREAK_RELATIVE_MARGIN:
                return False, "TOP1_CLEAR_LEAD"
            if understanding.primary_intent not in {
                "DIAGNOSIS", "CAUSE", "TROUBLESHOOTING", "SAFETY", "COMMUNICATION", "ALARM",
            }:
                return False, "INTENT_NOT_ELIGIBLE"
        return True, None

    @staticmethod
    def _validate_boundary(patch: CandidateTieBreakPatch, aliases: set[str]) -> str | None:
        ordered = list(patch.ordered_candidate_ids)
        score_ids = [item.candidate_id for item in patch.scores]
        if any(value not in aliases for value in [*ordered, *score_ids]):
            return "UNKNOWN_CANDIDATE_ID"
        if len(ordered) != len(set(ordered)) or len(score_ids) != len(set(score_ids)):
            return "DUPLICATE_CANDIDATE_ID"
        return None

    @staticmethod
    def _apply_order(
        original: list[QueryAwareCandidate],
        aliases: dict[str, QueryAwareCandidate],
        ordered_aliases: list[str],
        diagnostics: dict[str, Any],
    ) -> MiniMaxTieBreakResult:
        deterministic_ids = [item.candidate_id for item in original]
        ordered_shortlist = [aliases[value] for value in ordered_aliases if value in aliases]
        ordered_ids = {item.candidate_id for item in ordered_shortlist}
        ranked = ordered_shortlist + [item for item in original if item.candidate_id not in ordered_ids]
        ranked_ids = [item.candidate_id for item in ranked]
        valid_boundary = set(ranked_ids) == set(deterministic_ids) and len(ranked_ids) == len(deterministic_ids)
        if not valid_boundary:
            diagnostics.update({
                "structured_success": False,
                "provider_fallback": True,
                "fallback_reason": "SCHEMA_VALIDATION_FAILED",
                "fallback_order_preserved": True,
            })
            return MiniMaxTieBreakResult(original, diagnostics)
        diagnostics.update({
            "candidates_out": len(ranked),
            "order_changed": ranked_ids != deterministic_ids,
            "fallback_order_preserved": not diagnostics.get("provider_fallback", False),
        })
        return MiniMaxTieBreakResult(ranked, diagnostics)

    @staticmethod
    def _prompt(
        understanding: QueryUnderstandingResult,
        aliases: dict[str, QueryAwareCandidate],
    ) -> str:
        payload = {
            "question": understanding.canonical_question,
            "intent": understanding.primary_intent,
            "confirmed_facts": understanding.confirmed_facts,
            "normalized_semantics": understanding.normalized_semantics,
            "candidates": [
                {
                    "short_candidate_id": alias,
                    "title": item.document_title[:100],
                    "heading": (item.section_title or "")[:100],
                    "semantic_unit_type": "SEMANTIC_UNIT" if item.semantic_unit_id else "CHUNK",
                    "device_models": MiniMaxTieBreakService._metadata_values(item, "device_models", "device_model"),
                    "alarm_codes": MiniMaxTieBreakService._metadata_values(item, "alarm_codes", "alarm_code"),
                    "evidence_summary": " ".join((item.content or "").split())[:180],
                    "condition_summary": " ".join(
                        term for term in understanding.conditions if term.lower() in (item.content or "").lower()
                    )[:100],
                    "source_type": "PDF" if item.page_number is not None else "HTML",
                    "citation_valid": bool(item.scope_validation_passed and (item.page_number is not None or item.section_title or item.source_locator)),
                }
                for alias, item in aliases.items()
            ],
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _metadata_values(item: QueryAwareCandidate, *keys: str) -> list[str]:
        output: list[str] = []
        for source in (getattr(item.chunk, "metadata_json", None), getattr(item.document, "metadata_json", None)):
            if not isinstance(source, dict):
                continue
            for key in keys:
                value = source.get(key)
                values = value if isinstance(value, list) else [value] if value else []
                output.extend(str(entry) for entry in values)
        return list(dict.fromkeys(output))[:6]
