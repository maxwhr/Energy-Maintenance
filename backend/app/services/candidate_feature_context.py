from __future__ import annotations


class CandidateFeatureContext:
    """Captures features already computed by deterministic rerank for downstream reuse."""

    def __init__(self):
        self._features: dict[str, dict] = {}

    def capture(self, candidates: list) -> dict:
        for item in candidates:
            self._features[item.candidate_id] = {
                "exact_model_match": item.exact_model_match,
                "exact_alarm_match": item.exact_alarm_match,
                "requested_information_support": sorted(item.requested_information_support),
                "requested_information_coverage": item.requested_information_coverage,
                "direct_answer_score": item.direct_answer_score,
                "direct_answer_level": item.direct_answer_level,
                "generality_penalty": item.generality_penalty,
                "channel_votes": sorted(item.source_channels),
            }
        return {
            "candidate_count": len(self._features),
            "feature_calculations_reused": len(self._features),
            "benchmark_relevance_used": False,
        }

    def get(self, candidate_id: str) -> dict | None:
        return self._features.get(candidate_id)
