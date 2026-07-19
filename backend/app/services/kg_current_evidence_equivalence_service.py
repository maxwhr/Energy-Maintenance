from __future__ import annotations

from typing import Any

from app.services.knowledge_graph_fact_identity_service import KnowledgeGraphFactIdentityService
from app.services.kg_relation_evidence_type_matrix import KGRelationEvidenceTypeMatrix


class KGCurrentEvidenceEquivalenceService:
    """Deterministic fact/evidence equivalence gate used before any write plan."""

    VERSION = "task25g_r2_current_evidence_equivalence_v1"

    @staticmethod
    def _compatible(expected: str | None, actual: str | None, *, exact_term_match: bool = False) -> bool:
        if not expected:
            return True
        if exact_term_match:
            return True
        if not actual:
            return False
        return KnowledgeGraphFactIdentityService.normalize_key(expected) == KnowledgeGraphFactIdentityService.normalize_key(actual)

    def evaluate(self, fact: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
        fact_kind = fact["fact_kind"]
        semantic_type = str(candidate.get("semantic_unit_type") or "")
        subject_match = bool(candidate.get("subject_match"))
        object_match = bool(candidate.get("object_match")) if fact_kind == "EDGE" else True
        relation_match = bool(candidate.get("relation_match")) if fact_kind == "EDGE" else True
        type_compatible = (
            KGRelationEvidenceTypeMatrix.node_type_compatible(fact["node_type"], semantic_type)
            if fact_kind == "NODE"
            else KGRelationEvidenceTypeMatrix.relation_type_compatible(fact["relation_type"], semantic_type)
        )
        checks = {
            "subject_normalized_identity_exact": subject_match,
            "object_normalized_identity_exact": object_match,
            "relation_type_compatible": type_compatible and relation_match,
            "product_family_compatible": self._compatible(
                fact.get("product_family"),
                candidate.get("product_family"),
                exact_term_match=bool(candidate.get("product_family_term_match")),
            ),
            "model_compatible": self._compatible(
                fact.get("device_model"),
                candidate.get("device_model"),
                exact_term_match=bool(candidate.get("model_term_match")),
            ),
            "alarm_compatible": self._compatible(
                fact.get("alarm_code"),
                candidate.get("alarm_code"),
                exact_term_match=bool(candidate.get("alarm_term_match")),
            ),
            "component_compatible": self._compatible(
                fact.get("component"),
                candidate.get("component"),
                exact_term_match=bool(candidate.get("component_term_match")),
            ),
            "requested_fact_type_compatible": type_compatible,
            "source_document_current": bool(candidate.get("document_current")),
            "source_language_chinese": str(candidate.get("language") or "").lower() in {"zh", "zh-cn", "zh_cn"},
            "source_engineering_approved": bool(candidate.get("engineering_approved")),
            "source_locator_valid": bool(candidate.get("locator_valid")),
            "source_text_not_contradicted": not bool(candidate.get("conflict")),
            "no_incompatible_entity_conflict": not bool(candidate.get("entity_conflict")),
        }
        passed = all(checks.values())
        return {
            "version": self.VERSION,
            "passed": passed,
            "checks": checks,
            "failure_reasons": [name for name, value in checks.items() if not value],
        }
