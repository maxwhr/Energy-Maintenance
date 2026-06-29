from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import KGCandidate, KGEdge, KGEvidenceLink, KGExtractionRun, KGNode, KGNodeAlias


class KnowledgeGraphRepository:
    def __init__(self, db: Session):
        self.db = db

    def count_nodes(self, *filters: Any) -> int:
        return self._count(KGNode, *filters)

    def count_edges(self, *filters: Any) -> int:
        return self._count(KGEdge, *filters)

    def count_evidence(self, *filters: Any) -> int:
        return self._count(KGEvidenceLink, *filters)

    def count_candidates(self, *filters: Any) -> int:
        return self._count(KGCandidate, *filters)

    def count_runs(self, *filters: Any) -> int:
        return self._count(KGExtractionRun, *filters)

    def node_type_counts(self) -> dict[str, int]:
        statement = (
            select(KGNode.node_type, func.count())
            .where(KGNode.status == "active")
            .group_by(KGNode.node_type)
            .order_by(KGNode.node_type.asc())
        )
        return {str(node_type): int(count) for node_type, count in self.db.execute(statement)}

    def relation_type_counts(self) -> dict[str, int]:
        statement = (
            select(KGEdge.relation_type, func.count())
            .where(KGEdge.status == "active")
            .group_by(KGEdge.relation_type)
            .order_by(KGEdge.relation_type.asc())
        )
        return {str(relation_type): int(count) for relation_type, count in self.db.execute(statement)}

    def create_node(self, node: KGNode) -> KGNode:
        self.db.add(node)
        self.db.flush()
        self.db.refresh(node)
        return node

    def find_node(
        self,
        *,
        node_type: str,
        canonical_name: str,
        manufacturer: str | None,
        product_series: str | None,
        device_type: str,
        include_archived: bool = False,
    ) -> KGNode | None:
        filters = [
            KGNode.node_type == node_type,
            KGNode.canonical_name == canonical_name,
            KGNode.manufacturer.is_(None) if manufacturer is None else KGNode.manufacturer == manufacturer,
            KGNode.product_series.is_(None) if product_series is None else KGNode.product_series == product_series,
            KGNode.device_type == device_type,
        ]
        if not include_archived:
            filters.append(KGNode.status != "archived")
        return self.db.scalar(select(KGNode).where(*filters))

    def get_node(self, node_id: UUID, *, include_archived: bool = False) -> KGNode | None:
        statement = (
            select(KGNode)
            .options(selectinload(KGNode.aliases), selectinload(KGNode.evidence_links))
            .where(KGNode.id == node_id)
        )
        if not include_archived:
            statement = statement.where(KGNode.status != "archived")
        return self.db.scalar(statement)

    def list_nodes(
        self,
        *,
        node_type: str | None = None,
        manufacturer: str | None = None,
        product_series: str | None = None,
        device_type: str | None = None,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[KGNode], int]:
        filters = self._node_filters(
            node_type=node_type,
            manufacturer=manufacturer,
            product_series=product_series,
            device_type=device_type,
            status=status,
            keyword=keyword,
        )
        total = self._count(KGNode, *filters)
        statement = (
            select(KGNode)
            .options(selectinload(KGNode.aliases), selectinload(KGNode.evidence_links))
            .where(*filters)
            .order_by(KGNode.updated_at.desc(), KGNode.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(statement)), total

    def update_node(self, node: KGNode) -> KGNode:
        self.db.add(node)
        self.db.flush()
        self.db.refresh(node)
        return node

    def create_alias(self, alias: KGNodeAlias) -> KGNodeAlias:
        self.db.add(alias)
        self.db.flush()
        return alias

    def replace_aliases(self, node: KGNode, aliases: Sequence[str], *, source_type: str | None = None) -> None:
        for alias in list(node.aliases):
            self.db.delete(alias)
        self.db.flush()
        self.add_aliases(node.id, aliases, source_type=source_type)

    def add_aliases(self, node_id: UUID, aliases: Sequence[str], *, source_type: str | None = None) -> None:
        seen = {
            alias.normalized_alias
            for alias in self.db.scalars(select(KGNodeAlias).where(KGNodeAlias.node_id == node_id))
        }
        for alias in aliases:
            cleaned = alias.strip()
            normalized = self.normalize_name(cleaned)
            if not cleaned or normalized in seen:
                continue
            self.db.add(
                KGNodeAlias(
                    node_id=node_id,
                    alias=cleaned,
                    normalized_alias=normalized,
                    source_type=source_type,
                )
            )
            seen.add(normalized)
        self.db.flush()

    def create_edge(self, edge: KGEdge) -> KGEdge:
        self.db.add(edge)
        self.db.flush()
        self.db.refresh(edge)
        return edge

    def find_edge(
        self,
        *,
        source_node_id: UUID,
        target_node_id: UUID,
        relation_type: str,
        include_archived: bool = False,
    ) -> KGEdge | None:
        filters = [
            KGEdge.source_node_id == source_node_id,
            KGEdge.target_node_id == target_node_id,
            KGEdge.relation_type == relation_type,
        ]
        if not include_archived:
            filters.append(KGEdge.status != "archived")
        return self.db.scalar(select(KGEdge).where(*filters))

    def get_edge(self, edge_id: UUID, *, include_archived: bool = False) -> KGEdge | None:
        statement = (
            select(KGEdge)
            .options(selectinload(KGEdge.source_node), selectinload(KGEdge.target_node), selectinload(KGEdge.evidence_links))
            .where(KGEdge.id == edge_id)
        )
        if not include_archived:
            statement = statement.where(KGEdge.status != "archived")
        return self.db.scalar(statement)

    def list_edges(
        self,
        *,
        source_node_id: UUID | None = None,
        target_node_id: UUID | None = None,
        relation_type: str | None = None,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[KGEdge], int]:
        filters = self._edge_filters(
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relation_type=relation_type,
            status=status,
            keyword=keyword,
        )
        total = self._count(KGEdge, *filters)
        statement = (
            select(KGEdge)
            .options(selectinload(KGEdge.source_node), selectinload(KGEdge.target_node), selectinload(KGEdge.evidence_links))
            .where(*filters)
            .order_by(KGEdge.updated_at.desc(), KGEdge.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(statement)), total

    def update_edge(self, edge: KGEdge) -> KGEdge:
        self.db.add(edge)
        self.db.flush()
        self.db.refresh(edge)
        return edge

    def create_evidence(self, evidence: KGEvidenceLink) -> KGEvidenceLink:
        self.db.add(evidence)
        self.db.flush()
        self.db.refresh(evidence)
        return evidence

    def list_evidence(
        self,
        *,
        node_id: UUID | None = None,
        edge_id: UUID | None = None,
        source_type: str | None = None,
        document_id: UUID | None = None,
        chunk_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[KGEvidenceLink], int]:
        filters = []
        if node_id:
            filters.append(KGEvidenceLink.node_id == node_id)
        if edge_id:
            filters.append(KGEvidenceLink.edge_id == edge_id)
        if source_type:
            filters.append(KGEvidenceLink.source_type == source_type)
        if document_id:
            filters.append(KGEvidenceLink.document_id == document_id)
        if chunk_id:
            filters.append(KGEvidenceLink.chunk_id == chunk_id)
        total = self._count(KGEvidenceLink, *filters)
        statement = (
            select(KGEvidenceLink)
            .where(*filters)
            .order_by(KGEvidenceLink.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(statement)), total

    def create_run(self, run: KGExtractionRun) -> KGExtractionRun:
        self.db.add(run)
        self.db.flush()
        self.db.refresh(run)
        return run

    def get_run(self, run_id: UUID) -> KGExtractionRun | None:
        return self.db.scalar(
            select(KGExtractionRun)
            .options(selectinload(KGExtractionRun.candidates))
            .where(KGExtractionRun.id == run_id)
        )

    def list_runs(
        self,
        *,
        source_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[KGExtractionRun], int]:
        filters = []
        if source_type:
            filters.append(KGExtractionRun.source_type == source_type)
        if status:
            filters.append(KGExtractionRun.status == status)
        total = self._count(KGExtractionRun, *filters)
        statement = (
            select(KGExtractionRun)
            .where(*filters)
            .order_by(KGExtractionRun.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(statement)), total

    def update_run(self, run: KGExtractionRun) -> KGExtractionRun:
        self.db.add(run)
        self.db.flush()
        self.db.refresh(run)
        return run

    def create_candidates(self, candidates: Sequence[KGCandidate]) -> list[KGCandidate]:
        if not candidates:
            return []
        self.db.add_all(list(candidates))
        self.db.flush()
        return list(candidates)

    def get_candidate(self, candidate_id: UUID) -> KGCandidate | None:
        return self.db.scalar(select(KGCandidate).where(KGCandidate.id == candidate_id))

    def list_candidates(
        self,
        *,
        run_id: UUID | None = None,
        candidate_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[KGCandidate], int]:
        filters = []
        if run_id:
            filters.append(KGCandidate.run_id == run_id)
        if candidate_type:
            filters.append(KGCandidate.candidate_type == candidate_type)
        if status:
            filters.append(KGCandidate.status == status)
        total = self._count(KGCandidate, *filters)
        statement = (
            select(KGCandidate)
            .where(*filters)
            .order_by(KGCandidate.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(statement)), total

    def update_candidate(self, candidate: KGCandidate) -> KGCandidate:
        self.db.add(candidate)
        self.db.flush()
        self.db.refresh(candidate)
        return candidate

    def neighborhood_edges(self, node_id: UUID, *, depth: int = 1, limit: int = 80) -> list[KGEdge]:
        current = {node_id}
        visited = {node_id}
        edges: list[KGEdge] = []
        for _ in range(depth):
            if not current:
                break
            statement = (
                select(KGEdge)
                .options(selectinload(KGEdge.source_node), selectinload(KGEdge.target_node))
                .where(
                    KGEdge.status == "active",
                    or_(KGEdge.source_node_id.in_(current), KGEdge.target_node_id.in_(current)),
                )
                .limit(limit)
            )
            level_edges = list(self.db.scalars(statement))
            next_nodes: set[UUID] = set()
            for edge in level_edges:
                edges.append(edge)
                for related_id in (edge.source_node_id, edge.target_node_id):
                    if related_id not in visited:
                        visited.add(related_id)
                        next_nodes.add(related_id)
            current = next_nodes
            if len(edges) >= limit:
                break
        unique: dict[UUID, KGEdge] = {}
        for edge in edges:
            unique[edge.id] = edge
        return list(unique.values())[:limit]

    def active_edges_for_nodes(self, node_ids: set[UUID]) -> list[KGEdge]:
        if not node_ids:
            return []
        return list(
            self.db.scalars(
                select(KGEdge)
                .options(selectinload(KGEdge.source_node), selectinload(KGEdge.target_node))
                .where(
                    KGEdge.status == "active",
                    KGEdge.source_node_id.in_(node_ids),
                    KGEdge.target_node_id.in_(node_ids),
                )
            )
        )

    def graph_nodes(
        self,
        *,
        node_type: str | None = None,
        manufacturer: str | None = None,
        product_series: str | None = None,
        device_type: str | None = None,
        keyword: str | None = None,
        limit: int = 80,
    ) -> list[KGNode]:
        filters = self._node_filters(
            node_type=node_type,
            manufacturer=manufacturer,
            product_series=product_series,
            device_type=device_type,
            status="active",
            keyword=keyword,
        )
        statement = (
            select(KGNode)
            .options(selectinload(KGNode.aliases), selectinload(KGNode.evidence_links))
            .where(*filters)
            .order_by(KGNode.confidence.desc(), KGNode.updated_at.desc(), KGNode.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement))

    def graph_edges(
        self,
        *,
        relation_type: str | None = None,
        keyword: str | None = None,
        limit: int = 120,
    ) -> list[KGEdge]:
        filters = self._edge_filters(
            source_node_id=None,
            target_node_id=None,
            relation_type=relation_type,
            status="active",
            keyword=keyword,
        )
        statement = (
            select(KGEdge)
            .options(selectinload(KGEdge.source_node), selectinload(KGEdge.target_node), selectinload(KGEdge.evidence_links))
            .where(*filters)
            .order_by(KGEdge.confidence.desc(), KGEdge.updated_at.desc(), KGEdge.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement))

    def search_active_nodes(
        self,
        *,
        keywords: Sequence[str],
        manufacturer: str | None = None,
        product_series: str | None = None,
        device_type: str | None = None,
        node_types: set[str] | None = None,
        limit: int = 30,
    ) -> list[KGNode]:
        filters: list[Any] = [KGNode.status == "active"]
        if manufacturer:
            filters.append(or_(KGNode.manufacturer == manufacturer, KGNode.manufacturer.is_(None)))
        if product_series:
            filters.append(or_(KGNode.product_series == product_series, KGNode.product_series.is_(None)))
        if device_type:
            filters.append(KGNode.device_type == device_type)
        if node_types:
            filters.append(KGNode.node_type.in_(node_types))
        keyword_filters = []
        for keyword in keywords:
            cleaned = keyword.strip()
            if len(cleaned) < 2:
                continue
            pattern = f"%{cleaned}%"
            keyword_filters.append(
                or_(
                    KGNode.canonical_name.ilike(pattern),
                    KGNode.display_name.ilike(pattern),
                    KGNode.aliases.any(KGNodeAlias.alias.ilike(pattern)),
                )
            )
        if keyword_filters:
            filters.append(or_(*keyword_filters))
        statement = (
            select(KGNode)
            .options(selectinload(KGNode.aliases), selectinload(KGNode.evidence_links))
            .where(*filters)
            .order_by(KGNode.confidence.desc(), KGNode.updated_at.desc(), KGNode.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement))

    def search_active_edges(
        self,
        *,
        keywords: Sequence[str],
        relation_type: str | None = None,
        limit: int = 30,
    ) -> list[KGEdge]:
        filters: list[Any] = [KGEdge.status == "active"]
        if relation_type:
            filters.append(KGEdge.relation_type == relation_type)
        keyword_filters = []
        for keyword in keywords:
            cleaned = keyword.strip()
            if len(cleaned) < 2:
                continue
            pattern = f"%{cleaned}%"
            keyword_filters.append(or_(KGEdge.relation_type.ilike(pattern), KGEdge.display_relation.ilike(pattern)))
        if keyword_filters:
            filters.append(or_(*keyword_filters))
        statement = (
            select(KGEdge)
            .options(selectinload(KGEdge.source_node), selectinload(KGEdge.target_node), selectinload(KGEdge.evidence_links))
            .where(*filters)
            .order_by(KGEdge.confidence.desc(), KGEdge.updated_at.desc(), KGEdge.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement))

    @staticmethod
    def normalize_name(value: str) -> str:
        return " ".join(value.strip().lower().split())

    def _node_filters(
        self,
        *,
        node_type: str | None,
        manufacturer: str | None,
        product_series: str | None,
        device_type: str | None,
        status: str | None,
        keyword: str | None,
    ) -> list[Any]:
        filters = []
        if node_type:
            filters.append(KGNode.node_type == node_type)
        if manufacturer:
            filters.append(KGNode.manufacturer == manufacturer)
        if product_series:
            filters.append(KGNode.product_series == product_series)
        if device_type:
            filters.append(KGNode.device_type == device_type)
        if status:
            filters.append(KGNode.status == status)
        else:
            filters.append(KGNode.status != "archived")
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(or_(KGNode.canonical_name.ilike(pattern), KGNode.display_name.ilike(pattern)))
        return filters

    def _edge_filters(
        self,
        *,
        source_node_id: UUID | None,
        target_node_id: UUID | None,
        relation_type: str | None,
        status: str | None,
        keyword: str | None,
    ) -> list[Any]:
        filters = []
        if source_node_id:
            filters.append(KGEdge.source_node_id == source_node_id)
        if target_node_id:
            filters.append(KGEdge.target_node_id == target_node_id)
        if relation_type:
            filters.append(KGEdge.relation_type == relation_type)
        if status:
            filters.append(KGEdge.status == status)
        else:
            filters.append(KGEdge.status != "archived")
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(or_(KGEdge.relation_type.ilike(pattern), KGEdge.display_relation.ilike(pattern)))
        return filters

    def _count(self, model: Any, *filters: Any) -> int:
        statement = select(func.count()).select_from(model)
        if filters:
            statement = statement.where(*filters)
        return self.db.scalar(statement) or 0
