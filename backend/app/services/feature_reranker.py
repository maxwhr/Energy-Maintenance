from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RerankFeatures:
    keyword_score: float = 0.0
    vector_score: float = 0.0
    exact_device_model: float = 0.0
    exact_fault_code: float = 0.0
    heading_match: float = 0.0
    section_type_match: float = 0.0
    kg_alias_match: float = 0.0
    document_status: float = 1.0
    document_version: float = 1.0
    duplicate_penalty: float = 0.0
    diversity_penalty: float = 0.0
    query_intent_match: float = 0.0


class FeatureFusionReranker:
    VERSION = "feature_fusion_v2"
    DEFAULT_WEIGHTS = {
        "keyword_score": 0.34, "vector_score": 0.10, "exact_device_model": 0.18,
        "exact_fault_code": 0.20, "heading_match": 0.07, "section_type_match": 0.03,
        "kg_alias_match": 0.02, "document_status": 0.02, "document_version": 0.01,
        "query_intent_match": 0.05, "duplicate_penalty": -0.10, "diversity_penalty": -0.04,
    }

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = {**self.DEFAULT_WEIGHTS, **(weights or {})}

    def score(self, features: RerankFeatures) -> float:
        raw = sum(getattr(features, name) * weight for name, weight in self.weights.items())
        return round(max(0.0, min(1.0, raw)), 6)

    def snapshot(self) -> dict:
        return {"version": self.VERSION, "weights": dict(self.weights), "test_split_tuning_allowed": False}

    @staticmethod
    def should_rollback(hybrid_ndcg: float, rerank_ndcg: float) -> bool:
        return rerank_ndcg < hybrid_ndcg - 0.01
