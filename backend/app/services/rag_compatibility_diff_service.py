from __future__ import annotations

from typing import Any

from app.services.rag_compatibility_replay_service import RagReplayResult
from app.services.rag_raw_channel_snapshot import stable_hash


STAGE_ORDER = (
    "QUERY_UNDERSTANDING",
    "QUERY_VARIANTS",
    "CHANNEL_REQUEST",
    "CHANNEL_RAW_RESULT",
    "CHANNEL_NORMALIZATION",
    "CANDIDATE_MAPPING",
    "EVIDENCE_IDENTITY",
    "DEDUP",
    "RRF",
    "DETERMINISTIC_RERANK",
    "POST_GUARD",
    "REFINEMENT",
    "HYDRATION",
    "CITATION",
    "CONFIDENCE",
    "SERIALIZATION",
)


class RagCompatibilityDiffService:
    REASON_BY_STAGE = {
        "QUERY_UNDERSTANDING": "UNKNOWN",
        "QUERY_VARIANTS": "UNKNOWN",
        "CHANNEL_REQUEST": "UNKNOWN",
        "CHANNEL_RAW_RESULT": "PROVIDER_RESPONSE_VARIANCE",
        "CHANNEL_NORMALIZATION": "ASYNC_COMPLETION_ORDER",
        "CANDIDATE_MAPPING": "IDENTITY_MAPPING_DIFFERENCE",
        "EVIDENCE_IDENTITY": "IDENTITY_MAPPING_DIFFERENCE",
        "DEDUP": "CHANNEL_VOTE_ORDER",
        "RRF": "UNSTABLE_TIE_BREAK",
        "DETERMINISTIC_RERANK": "UNSTABLE_TIE_BREAK",
        "POST_GUARD": "REFINEMENT_ORDER_DIFFERENCE",
        "REFINEMENT": "REFINEMENT_ORDER_DIFFERENCE",
        "HYDRATION": "HYDRATION_MISSING_RECORD",
        "CITATION": "CITATION_EXPANSION_DIFFERENCE",
        "CONFIDENCE": "CITATION_EXPANSION_DIFFERENCE",
        "SERIALIZATION": "SERIALIZATION_ORDER_DIFFERENCE",
    }

    def compare(self, reference: RagReplayResult, optimized: RagReplayResult) -> dict[str, Any]:
        if reference.case_id != optimized.case_id:
            raise ValueError("replay case mismatch")
        stage_checks = []
        first = None
        for stage in STAGE_ORDER:
            reference_value = reference.stages.get(stage)
            optimized_value = optimized.stages.get(stage)
            equal = reference_value == optimized_value
            stage_checks.append({
                "stage": stage,
                "equal": equal,
                "reference_hash": stable_hash(reference_value),
                "optimized_hash": stable_hash(optimized_value),
            })
            if not equal and first is None:
                first = stage
        reference_ids = self._strings(reference.stages.get(first)) if first else set()
        optimized_ids = self._strings(optimized.stages.get(first)) if first else set()
        return {
            "case_id": reference.case_id,
            "first_divergent_stage": first,
            "reference_hash": stable_hash(reference.output),
            "optimized_hash": stable_hash(optimized.output),
            "missing_ids": sorted(reference_ids - optimized_ids)[:100],
            "added_ids": sorted(optimized_ids - reference_ids)[:100],
            "rank_changes": self._rank_changes(reference.output, optimized.output),
            "citation_changes": {
                "identity": reference.output.get("citation_identities") != optimized.output.get("citation_identities"),
                "locator": reference.output.get("citation_locators") != optimized.output.get("citation_locators"),
            },
            "channel_status_changes": reference.output.get("actual_channels") != optimized.output.get("actual_channels"),
            "reason": self.REASON_BY_STAGE.get(first, "UNKNOWN") if first else "NO_DIFFERENCE",
            "severity": "P0" if first else "NONE",
            "fix_required": bool(first),
            "stages": stage_checks,
        }

    @staticmethod
    def _strings(value: Any) -> set[str]:
        output: set[str] = set()
        if isinstance(value, dict):
            for key, item in value.items():
                output.add(str(key))
                output.update(RagCompatibilityDiffService._strings(item))
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                output.update(RagCompatibilityDiffService._strings(item))
        elif value is not None:
            output.add(str(value))
        return output

    @staticmethod
    def _rank_changes(reference: dict[str, Any], optimized: dict[str, Any]) -> list[dict[str, Any]]:
        left = reference.get("rerank_order") or []
        right = optimized.get("rerank_order") or []
        left_rank = {value: index + 1 for index, value in enumerate(left)}
        right_rank = {value: index + 1 for index, value in enumerate(right)}
        return [
            {"candidate_id": candidate_id, "reference_rank": left_rank[candidate_id], "optimized_rank": right_rank[candidate_id]}
            for candidate_id in sorted(left_rank.keys() & right_rank.keys())
            if left_rank[candidate_id] != right_rank[candidate_id]
        ][:100]
