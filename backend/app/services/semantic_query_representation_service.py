from __future__ import annotations

from dataclasses import asdict, dataclass

from app.services.query_understanding_service import QueryUnderstandingService


@dataclass(frozen=True, slots=True)
class SemanticQueryRepresentation:
    normalized_query: str
    symptom_terms: list[str]
    cause_terms: list[str]
    action_terms: list[str]
    safety_terms: list[str]
    component_terms: list[str]
    product_context: list[str]
    semantic_query_text: str

    def public_dict(self) -> dict:
        return asdict(self)


class SemanticQueryRepresentationService:
    """Traceable query normalization; it never consumes expected labels or document titles."""

    def __init__(self) -> None:
        self.understanding = QueryUnderstandingService()

    @staticmethod
    def semantic_route_for_vector_heavy(*, semantic_partition_available: bool) -> tuple[str, bool, str | None]:
        if semantic_partition_available:
            return "semantic_vector", False, None
        return "semantic_vector", False, "semantic_partition_unavailable"

    def build(self, query: str) -> SemanticQueryRepresentation:
        analysis = self.understanding.understand(query)
        symptoms = list(dict.fromkeys([*analysis.symptom_terms, *analysis.fault_names]))
        actions = [term for term in analysis.expanded_terms if term in {"检查", "测量", "设置", "更换", "断开", "连接", "确认"}]
        components = list(dict.fromkeys(analysis.component_terms))
        product = list(dict.fromkeys(analysis.device_models))
        text = "\n".join((
            f"原始问题：{analysis.normalized_query}", f"故障现象：{'、'.join(symptoms)}",
            "可能原因：", f"处理动作：{'、'.join(actions)}", f"安全要求：{'、'.join(analysis.safety_terms)}",
            f"部件：{'、'.join(components)}", f"产品上下文：{'、'.join(product)}",
        ))
        return SemanticQueryRepresentation(
            normalized_query=analysis.normalized_query, symptom_terms=symptoms, cause_terms=[], action_terms=actions,
            safety_terms=list(analysis.safety_terms), component_terms=components, product_context=product,
            semantic_query_text=text,
        )
