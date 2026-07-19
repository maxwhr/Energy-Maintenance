from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import KGNode, KGNodeAlias
from app.repositories.knowledge_graph_repository import KnowledgeGraphRepository


@dataclass(frozen=True)
class KGAliasResolutionResult:
    resolved_node_id: UUID | None
    candidate_node_ids: tuple[UUID, ...]
    resolution_status: str
    required_context: tuple[str, ...]
    clarification_required: bool


class KGAliasResolutionPolicyService:
    """Deterministically resolves aliases only when supplied context is sufficient."""

    CONTEXT_FIELDS = ("node_type", "manufacturer", "product_series", "model", "alarm_code")

    def __init__(self, db: Session):
        self.db = db

    def resolve(self, alias: str, *, context: dict[str, Any] | None = None) -> KGAliasResolutionResult:
        normalized = KnowledgeGraphRepository.normalize_name(alias)
        nodes = list(
            self.db.scalars(
                select(KGNode)
                .join(KGNodeAlias, KGNodeAlias.node_id == KGNode.id)
                .options(selectinload(KGNode.aliases))
                .where(
                    KGNodeAlias.normalized_alias == normalized,
                    KGNode.status == "active",
                )
                .order_by(KGNode.id.asc())
            )
        )
        return self.resolve_candidates(nodes, context=context)

    @classmethod
    def resolve_candidates(
        cls,
        nodes: list[KGNode],
        *,
        context: dict[str, Any] | None = None,
    ) -> KGAliasResolutionResult:
        unique = {node.id: node for node in nodes}
        ordered = [unique[key] for key in sorted(unique, key=str)]
        if not ordered:
            return KGAliasResolutionResult(None, (), "NOT_FOUND", (), False)
        if len(ordered) == 1:
            return KGAliasResolutionResult(ordered[0].id, (ordered[0].id,), "SAFE_EQUIVALENT", (), False)
        context = {key: value for key, value in (context or {}).items() if value not in (None, "")}
        discriminators = cls._discriminating_fields(ordered)
        canonical_names = {KnowledgeGraphRepository.normalize_name(node.canonical_name) for node in ordered}
        signatures = {
            tuple(cls._value(node, field) for field in cls.CONTEXT_FIELDS)
            for node in ordered
        }
        if len(canonical_names) == 1 and len(signatures) == 1:
            selected = ordered[0]
            return KGAliasResolutionResult(
                selected.id,
                tuple(node.id for node in ordered),
                "SAFE_EQUIVALENT",
                (),
                False,
            )
        filtered = [node for node in ordered if cls._matches(node, context)] if context else ordered
        if len(filtered) == 1:
            return KGAliasResolutionResult(
                filtered[0].id,
                tuple(node.id for node in ordered),
                "CONTEXT_DEPENDENT",
                tuple(discriminators),
                False,
            )
        if not filtered:
            return KGAliasResolutionResult(
                None,
                tuple(node.id for node in ordered),
                "INCOMPATIBLE",
                tuple(discriminators),
                True,
            )
        status = "CONTEXT_DEPENDENT" if discriminators else "INCOMPATIBLE"
        return KGAliasResolutionResult(
            None,
            tuple(node.id for node in filtered),
            status,
            tuple(discriminators),
            True,
        )

    @classmethod
    def _discriminating_fields(cls, nodes: list[KGNode]) -> list[str]:
        result = []
        for field in cls.CONTEXT_FIELDS:
            values = {cls._value(node, field) for node in nodes}
            values.discard(None)
            if len(values) > 1:
                result.append(field)
        return result

    @classmethod
    def _matches(cls, node: KGNode, context: dict[str, Any]) -> bool:
        for key, expected in context.items():
            if key not in cls.CONTEXT_FIELDS:
                continue
            actual = cls._value(node, key)
            if actual is None or str(actual).lower() != str(expected).lower():
                return False
        return True

    @staticmethod
    def _value(node: KGNode, field: str) -> Any:
        if field in {"node_type", "manufacturer", "product_series"}:
            return getattr(node, field)
        return (node.properties_json or {}).get(field)
