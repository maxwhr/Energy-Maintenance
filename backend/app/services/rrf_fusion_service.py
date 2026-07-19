from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.services.evidence_identity_service import EvidenceIdentityService


@dataclass(slots=True)
class QueryAwareCandidate:
    candidate_id: str
    chunk_id: str
    document_id: str
    document_title: str
    content: str
    section_title: str | None = None
    page_number: int | None = None
    chunk: Any = None
    document: Any = None
    source_channels: set[str] = field(default_factory=set)
    source_query_types: set[str] = field(default_factory=set)
    raw_ranks: dict[str, int] = field(default_factory=dict)
    raw_scores: dict[str, float] = field(default_factory=dict)
    rrf_score: float = 0.0
    rerank_score: float | None = None
    final_score: float = 0.0
    exact_model_match: bool = False
    exact_alarm_match: bool = False
    semantic_unit_id: str | None = None
    source_chunk_ids: list[str] = field(default_factory=list)
    source_locator: dict = field(default_factory=dict)
    scope_validation_passed: bool = False
    evidence_identity: str | None = None
    evidence_equivalence_key: str | None = None
    evidence_aliases: set[str] = field(default_factory=set)
    evidence_level: str = "CHUNK"
    requested_information_support: set[str] = field(default_factory=set)
    requested_information_coverage: float = 0.0
    direct_answer_score: float = 0.0
    direct_answer_level: str = "NON_SUPPORTING"
    generality_penalty: float = 0.0
    raw_relevance_score: float = 0.0
    normalized_relevance_score: float = 0.0
    repository_rank: int | None = None
    matched_fields: set[str] = field(default_factory=set)
    matched_tokens: set[str] = field(default_factory=set)
    exact_phrase_matches: set[str] = field(default_factory=set)
    exact_body_phrase_matches: set[str] = field(default_factory=set)
    score_source: str | None = None
    score_fallback_used: bool = False
    score_provenance: dict[str, dict[str, Any]] = field(default_factory=dict)

    def merge_from(self, other: "QueryAwareCandidate") -> None:
        self.source_channels.update(other.source_channels)
        self.source_query_types.update(other.source_query_types)
        self.raw_ranks.update({key: min(value, self.raw_ranks.get(key, value)) for key, value in other.raw_ranks.items()})
        self.raw_scores.update({key: max(value, self.raw_scores.get(key, value)) for key, value in other.raw_scores.items()})
        self.exact_model_match = self.exact_model_match or other.exact_model_match
        self.exact_alarm_match = self.exact_alarm_match or other.exact_alarm_match
        self.scope_validation_passed = self.scope_validation_passed and other.scope_validation_passed
        if not self.semantic_unit_id:
            self.semantic_unit_id = other.semantic_unit_id
            if other.semantic_unit_id:
                self.evidence_identity = other.evidence_identity or other.semantic_unit_id
                self.evidence_level = "SEMANTIC_UNIT"
        self.source_chunk_ids = list(dict.fromkeys([*self.source_chunk_ids, *other.source_chunk_ids]))
        self.evidence_aliases.update(other.evidence_aliases)
        self.requested_information_support.update(other.requested_information_support)
        self.requested_information_coverage = max(self.requested_information_coverage, other.requested_information_coverage)
        self.direct_answer_score = max(self.direct_answer_score, other.direct_answer_score)
        self.generality_penalty = min(self.generality_penalty, other.generality_penalty)
        self.raw_relevance_score = max(self.raw_relevance_score, other.raw_relevance_score)
        self.normalized_relevance_score = max(self.normalized_relevance_score, other.normalized_relevance_score)
        if other.repository_rank is not None:
            self.repository_rank = min(self.repository_rank or other.repository_rank, other.repository_rank)
        self.matched_fields.update(other.matched_fields)
        self.matched_tokens.update(other.matched_tokens)
        self.exact_phrase_matches.update(other.exact_phrase_matches)
        self.exact_body_phrase_matches.update(other.exact_body_phrase_matches)
        self.score_fallback_used = self.score_fallback_used or other.score_fallback_used
        self.score_provenance.update(other.score_provenance)
        if self.score_source is None:
            self.score_source = other.score_source


class RRFFusionService:
    def __init__(
        self, *, rrf_k: int = 60, exact_boost: float = 0.02,
        consistency_boost: float = 0.006, relevance_weight: float = 0.012,
    ):
        self.rrf_k = rrf_k
        self.exact_boost = exact_boost
        self.consistency_boost = consistency_boost
        self.relevance_weight = relevance_weight
        self.last_diagnostics: dict[str, Any] = {}

    def fuse(
        self,
        rankings: dict[str, list[QueryAwareCandidate]],
        *,
        top_k: int = 50,
        channel_weights: dict[str, float] | None = None,
        query_weights: dict[str, float] | None = None,
    ) -> list[QueryAwareCandidate]:
        merged: dict[str, QueryAwareCandidate] = {}
        best_votes: dict[str, dict[str, tuple[float, str, int, float, float, str]]] = defaultdict(dict)
        duplicate_votes_removed = 0
        channel_weights = channel_weights or {}
        query_weights = query_weights or {}
        identity_service = EvidenceIdentityService()
        for vote_key, candidates in rankings.items():
            parts = vote_key.split(":")
            channel = parts[0]
            query_type = parts[1] if len(parts) > 1 else "ORIGINAL"
            seen_in_vote: set[str] = set()
            for rank, candidate in enumerate(candidates, start=1):
                if not candidate.evidence_equivalence_key:
                    identity_service.apply(candidate)
                evidence_key = candidate.evidence_equivalence_key or candidate.candidate_id
                if evidence_key in seen_in_vote:
                    continue
                seen_in_vote.add(evidence_key)
                candidate.raw_ranks[vote_key] = rank
                if evidence_key not in merged:
                    merged[evidence_key] = candidate
                    merged[evidence_key].scope_validation_passed = candidate.scope_validation_passed
                else:
                    merged[evidence_key].merge_from(candidate)
                channel_weight = channel_weights.get(channel, 1.0)
                query_weight = query_weights.get(query_type, 1.0)
                reciprocal_contribution = channel_weight * query_weight / (self.rrf_k + rank)
                normalized_relevance = max(0.0, min(1.0, candidate.normalized_relevance_score))
                relevance_contribution = channel_weight * query_weight * normalized_relevance * self.relevance_weight
                weighted_vote = reciprocal_contribution + relevance_contribution
                previous = best_votes[evidence_key].get(channel)
                if previous is None or weighted_vote > previous[0]:
                    if previous is not None:
                        duplicate_votes_removed += 1
                    best_votes[evidence_key][channel] = (
                        weighted_vote, vote_key, rank, reciprocal_contribution,
                        relevance_contribution, self._query_family(query_type),
                    )
                else:
                    duplicate_votes_removed += 1
        for evidence_key, candidate in merged.items():
            score = sum(value[0] for value in best_votes[evidence_key].values())
            if candidate.exact_model_match or candidate.exact_alarm_match:
                score += self.exact_boost
            independent_channels = len(candidate.source_channels)
            score += min(0.018, max(0, independent_channels - 1) * self.consistency_boost)
            candidate.rrf_score = round(score, 8)
            candidate.final_score = candidate.rrf_score
        channel_priority = {
            "EXACT_KEYWORD": 0,
            "SCOPED_KEYWORD": 1,
            "RAW_VECTOR": 2,
            "SEMANTIC_UNIT": 3,
            "KG_ALIAS": 4,
        }
        output = sorted(
            merged.values(),
            key=lambda item: (
                -round(item.final_score, 8),
                min(
                    (
                        value[2]
                        for value in best_votes[item.evidence_equivalence_key or item.candidate_id].values()
                    ),
                    default=10**9,
                ),
                min((channel_priority.get(channel, 99) for channel in item.source_channels), default=99),
                item.evidence_equivalence_key or item.evidence_identity or item.candidate_id,
                item.candidate_id,
            ),
        )[:top_k]
        self.last_diagnostics = {
            "channel_vote_cap": 1,
            "duplicate_votes_removed": duplicate_votes_removed,
            "channel_weights_applied": bool(channel_weights),
            "query_weights_applied": bool(query_weights),
            "normalized_relevance_weight": self.relevance_weight,
            "candidate_count_before": sum(len(values) for values in rankings.values()),
            "candidate_count_after": len(output),
            "vote_breakdown": {
                merged[evidence_key].candidate_id: {
                    channel: {
                        "weighted_vote": round(value[0], 8), "vote_key": value[1], "rank": value[2],
                        "rrf_contribution": round(value[3], 8),
                        "normalized_relevance_contribution": round(value[4], 8),
                        "query_family": value[5],
                    }
                    for channel, value in channels.items()
                }
                for evidence_key, channels in best_votes.items()
            },
        }
        return output

    @staticmethod
    def _query_family(query_type: str) -> str:
        value = str(query_type or "ORIGINAL").upper()
        if value in {"ORIGINAL"}:
            return "ORIGINAL"
        if value in {"CANONICAL", "EXACT_CANONICAL"}:
            return "EXACT_CANONICAL"
        if "MODEL" in value:
            return "MODEL"
        if "ALARM" in value or "SYMPTOM" in value:
            return "ALARM"
        if "PARAMETER" in value:
            return "PARAMETER"
        if "CAUSE" in value:
            return "CAUSE"
        if "PROCEDURE" in value or "REQUEST" in value:
            return "PROCEDURE"
        if "SAFETY" in value:
            return "SAFETY"
        return "GENERIC_EXPANSION"
