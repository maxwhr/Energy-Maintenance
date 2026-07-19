from __future__ import annotations

from dataclasses import asdict, dataclass

from app.services.query_understanding_service import QueryUnderstanding


@dataclass(slots=True)
class AdaptiveRetrievalDecision:
    requested_strategy: str
    recommended_strategy: str
    actual_strategy: str
    fallback_strategy: str
    routing_reason: str
    keyword_weight: float
    vector_weight: float
    reranker_requested: bool

    def model_dump(self) -> dict:
        return asdict(self)


class AdaptiveRetrievalStrategy:
    """Conservative query router; no expected IDs or evaluation labels are used."""

    SUPPORTED = {"keyword", "vector", "hybrid", "hybrid_rerank", "adaptive"}
    VISUAL_TERMS = ("图片", "图像", "视觉", "铭牌", "告警屏", "外观", "OCR", "照片")

    def route(
        self,
        analysis: QueryUnderstanding,
        *,
        requested_strategy: str,
        reranker_enabled: bool,
    ) -> AdaptiveRetrievalDecision:
        requested = requested_strategy if requested_strategy in self.SUPPORTED else "keyword"
        if requested != "adaptive":
            actual = requested
            return AdaptiveRetrievalDecision(
                requested_strategy=requested,
                recommended_strategy=actual,
                actual_strategy=actual,
                fallback_strategy="keyword",
                routing_reason="explicit_user_strategy",
                keyword_weight=0.70 if actual.startswith("hybrid") else float(actual == "keyword"),
                vector_weight=0.30 if actual.startswith("hybrid") else float(actual == "vector"),
                reranker_requested=actual == "hybrid_rerank" and reranker_enabled,
            )

        query = analysis.normalized_query
        if analysis.fault_codes:
            actual, reason, weights = "keyword", "exact_fault_code_keyword_first", (1.0, 0.0)
        elif analysis.device_models and analysis.confidence >= 0.70:
            actual, reason, weights = "keyword", "exact_device_model_keyword_first", (1.0, 0.0)
        elif analysis.safety_terms or analysis.query_intent == "safety_operation":
            actual, reason, weights = "keyword", "safety_heading_keyword_first", (1.0, 0.0)
        elif any(term.lower() in query.lower() for term in self.VISUAL_TERMS):
            actual, reason, weights = "hybrid", "visual_descriptor_vector_enhanced", (0.35, 0.65)
        elif analysis.symptom_terms or analysis.query_intent == "fault_diagnosis":
            actual = "hybrid_rerank" if reranker_enabled else "hybrid"
            reason, weights = "semantic_symptom_vector_enhanced_hybrid", (0.30, 0.70)
        else:
            actual, reason, weights = "keyword", "conservative_keyword_default", (1.0, 0.0)
        return AdaptiveRetrievalDecision(
            requested_strategy=requested,
            recommended_strategy=actual,
            actual_strategy=actual,
            fallback_strategy="keyword",
            routing_reason=reason,
            keyword_weight=weights[0],
            vector_weight=weights[1],
            reranker_requested=actual == "hybrid_rerank" and reranker_enabled,
        )
