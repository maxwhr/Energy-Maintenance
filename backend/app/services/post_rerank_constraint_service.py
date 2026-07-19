from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.schemas.query_understanding import QueryUnderstandingResult
from app.services.deterministic_evidence_rerank_service import DeterministicEvidenceRerankService
from app.services.rrf_fusion_service import QueryAwareCandidate


@dataclass(frozen=True, slots=True)
class PostRerankConstraintResult:
    candidates: list[QueryAwareCandidate]
    diagnostics: dict[str, Any]


class PostRerankConstraintService:
    """Generic entity and answer-composition guards; no case-specific knowledge."""

    def apply(
        self,
        candidates: list[QueryAwareCandidate],
        *,
        understanding: QueryUnderstandingResult,
    ) -> PostRerankConstraintResult:
        original = list(candidates)
        positions = {item.candidate_id: index for index, item in enumerate(original)}
        required = set(understanding.requested_information)
        ranked = sorted(
            original,
            key=lambda item: (
                self._condition_conflict(item, understanding),
                -self._entity_priority(item, understanding),
                -self._required_support_count(item, required),
                positions[item.candidate_id],
            ),
        )
        movements: list[dict[str, Any]] = []
        if "CAUSE" in required and "ACTION" in required:
            self._ensure_top3(ranked, "CAUSE", movements)
            self._ensure_top3(ranked, "ACTION", movements)
        for requested in ("SAFETY", "PROCEDURE"):
            if requested in required:
                self._ensure_top3(ranked, requested, movements)
        ranked = self._diversify_actions(ranked, movements)
        original_ids = [item.candidate_id for item in original]
        ranked_ids = [item.candidate_id for item in ranked]
        if len(ranked_ids) != len(original_ids) or set(ranked_ids) != set(original_ids):
            return PostRerankConstraintResult(original, {
                "executed": True,
                "status": "POST_RERANK_CONSTRAINT_BOUNDARY_FALLBACK",
                "fallback": True,
                "candidate_additions": 0,
                "candidate_removals": 0,
                "source_modifications": 0,
            })
        return PostRerankConstraintResult(ranked, {
            "executed": True,
            "status": "POST_RERANK_CONSTRAINTS_APPLIED",
            "fallback": False,
            "order_changed": original_ids != ranked_ids,
            "candidate_additions": 0,
            "candidate_removals": 0,
            "source_modifications": 0,
            "citation_modifications": 0,
            "exact_model_guard": bool(understanding.device_models),
            "exact_alarm_guard": bool(understanding.alarm_codes or understanding.alarm_names),
            "cause_action_top3_guard": "CAUSE" in required and "ACTION" in required,
            "safety_procedure_guard": bool(required & {"SAFETY", "PROCEDURE"}),
            "condition_conflict_guard": bool(understanding.conditions),
            "action_diversity_guard": True,
            "movements": movements,
            "benchmark_labels_used": False,
        })

    @staticmethod
    def _entity_priority(item: QueryAwareCandidate, understanding: QueryUnderstandingResult) -> int:
        score = 0
        if understanding.device_models:
            score += 1 if item.exact_model_match else 0
        if understanding.alarm_codes or understanding.alarm_names:
            score += 1 if item.exact_alarm_match else 0
        return score

    @staticmethod
    def _required_support_count(item: QueryAwareCandidate, required: set[str]) -> int:
        support = set(item.requested_information_support)
        if not support:
            support = DeterministicEvidenceRerankService.requested_information_support(
                f"{item.section_title or ''} {item.content}", list(required)
            )
        return len(support & required)

    @staticmethod
    def _supports(item: QueryAwareCandidate, requested: str) -> bool:
        direct = DeterministicEvidenceRerankService.requested_information_support(
            item.content or "", [requested]
        )
        if requested in direct:
            return True
        return (
            requested in item.requested_information_support
            and item.direct_answer_level not in {"BACKGROUND_ONLY", "NON_SUPPORTING"}
        )

    @classmethod
    def _ensure_top3(cls, ranked: list[QueryAwareCandidate], requested: str, movements: list[dict[str, Any]]) -> None:
        if any(cls._supports(item, requested) for item in ranked[:3]):
            return
        index = next((idx for idx, item in enumerate(ranked[3:], start=3) if cls._supports(item, requested)), None)
        if index is None:
            return
        item = ranked.pop(index)
        ranked.insert(min(2, len(ranked)), item)
        movements.append({"candidate_id": item.candidate_id, "reason": f"{requested}_TOP3_REQUIRED"})

    @staticmethod
    def _diversify_actions(ranked: list[QueryAwareCandidate], movements: list[dict[str, Any]]) -> list[QueryAwareCandidate]:
        if len(ranked) < 3:
            return ranked
        identities: set[str] = set()
        diverse: list[QueryAwareCandidate] = []
        deferred: list[QueryAwareCandidate] = []
        for item in ranked:
            identity = item.evidence_identity or item.evidence_equivalence_key or item.semantic_unit_id or item.candidate_id
            if identity in identities:
                deferred.append(item)
            else:
                identities.add(identity)
                diverse.append(item)
        if deferred:
            movements.extend({"candidate_id": item.candidate_id, "reason": "DUPLICATE_ACTION_DEFERRED"} for item in deferred)
        return [*diverse, *deferred]

    @staticmethod
    def _condition_conflict(item: QueryAwareCandidate, understanding: QueryUnderstandingResult) -> int:
        if not understanding.conditions:
            return 0
        text = f"{item.section_title or ''} {item.content}".lower()
        negatives = ("不适用", "仅限", "不支持", "禁止用于")
        return int(any(term in text for term in negatives) and not any(value.lower() in text for value in understanding.conditions))
