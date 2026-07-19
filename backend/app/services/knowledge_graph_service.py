from __future__ import annotations

import re
from collections import deque
from typing import Any
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import KGCandidate, KGEdge, KGEvidenceLink, KGExtractionRun, KGNode, User
from app.repositories.knowledge_graph_repository import KnowledgeGraphRepository
from app.schemas.knowledge_graph import (
    KGEdgeCreate,
    KGEdgeUpdate,
    KGEvidenceCreate,
    KGExtractionRequest,
    KGNodeCreate,
    KGNodeMergeRequest,
    KGNodeUpdate,
)
from app.services.kg_candidate_service import KGCandidatePermissionError, KGCandidateService, KGCandidateServiceError
from app.services.kg_evidence_service import KGEvidenceService
from app.services.kg_extraction_service import KGExtractionPermissionError, KGExtractionService, KGExtractionServiceError
from app.services.knowledge_graph_production_scope_service import (
    KnowledgeGraphProductionScopeService,
    ProductionScopeEvaluation,
)


class KnowledgeGraphServiceError(ValueError):
    pass


class KnowledgeGraphPermissionError(PermissionError):
    pass


MANAGER_ROLES = {"admin", "expert"}
READ_ROLES = {"admin", "expert", "engineer", "viewer"}

NODE_LEGEND = {
    "manufacturer": "厂家",
    "product_series": "产品系列",
    "fault": "故障",
    "alarm": "告警",
    "component": "部件",
    "cause": "可能原因",
    "inspection_item": "排查项",
    "action": "处理措施",
    "tool": "工具",
    "part": "备件",
    "safety_risk": "安全风险",
    "sop_template": "SOP 模板",
    "knowledge_document": "知识文档",
    "knowledge_chunk": "知识切片",
}

RELATION_LEGEND = {
    "BELONGS_TO": "属于",
    "HAS_ALARM": "关联告警",
    "HAS_SYMPTOM": "表现为",
    "CAUSED_BY": "可能原因",
    "CHECK_BY": "排查方式",
    "RESOLVED_BY": "处理措施",
    "USES_TOOL": "使用工具",
    "REQUIRES_PART": "需要备件",
    "HAS_SAFETY_RISK": "安全风险",
    "GUIDED_BY_SOP": "作业规程",
    "MENTIONED_IN": "提及于",
    "DERIVED_FROM": "来源于",
    "RELATED_TO": "相关",
}

DOMAIN_TERMS = [
    "逆变器",
    "华为",
    "阳光电源",
    "SUN2000",
    "FusionSolar",
    "SG",
    "告警",
    "绝缘",
    "阻抗",
    "过温",
    "风扇",
    "通信",
    "离线",
    "MPPT",
    "组串",
    "低发电",
    "电网",
    "并网",
    "直流",
    "交流",
    "接地",
    "高压",
    "断电",
    "验电",
    "排查",
    "检修",
    "复位",
    "更换",
    "清理",
]

FAULT_TYPE_TERMS = {
    "low_insulation_resistance": ["low_insulation_resistance", "low_insulation", "绝缘阻抗低", "绝缘", "阻抗"],
    "low_insulation": ["low_insulation", "绝缘阻抗低", "绝缘", "阻抗"],
    "dc_abnormal": ["dc_abnormal", "直流", "DC", "组串"],
    "ac_overvoltage": ["ac_overvoltage", "交流过压", "过压", "电网"],
    "ac_undervoltage": ["ac_undervoltage", "交流欠压", "欠压", "电网"],
    "grid_connection_fault": ["grid_connection_fault", "grid_fault", "并网", "电网"],
    "grid_fault": ["grid_fault", "并网", "电网"],
    "over_temperature": ["over_temperature", "overtemperature", "过温", "温度", "风扇"],
    "overtemperature": ["overtemperature", "过温", "温度", "风扇"],
    "fan_fault": ["fan_fault", "风扇", "散热", "过温"],
    "communication_interruption": ["communication_interruption", "communication_fault", "通信", "离线"],
    "communication_fault": ["communication_fault", "通信", "离线"],
    "device_offline": ["device_offline", "离线", "通信"],
    "mppt_abnormal": ["mppt_abnormal", "mppt_low_power", "MPPT", "组串"],
    "mppt_low_power": ["mppt_low_power", "MPPT", "组串", "低发电"],
    "low_power_generation": ["low_power_generation", "低发电", "MPPT", "组串"],
    "alarm_code_query": ["alarm_code_query", "告警码", "告警代码"],
}


class KnowledgeGraphService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = KnowledgeGraphRepository(db)
        self.production_scope = KnowledgeGraphProductionScopeService(db)

    def overview(self, *, current_user: User) -> dict[str, Any]:
        self._require_read(current_user)
        recent_runs, _ = self.repository.list_runs(page=1, page_size=5)
        return {
            "node_count": self.repository.count_nodes(KGNode.status == "active"),
            "edge_count": self.repository.count_edges(KGEdge.status == "active"),
            "evidence_count": self.repository.count_evidence(),
            "pending_candidate_count": self.repository.count_candidates(KGCandidate.status == "pending"),
            "completed_run_count": self.repository.count_runs(KGExtractionRun.status == "completed"),
            "node_type_counts": self.repository.node_type_counts(),
            "relation_type_counts": self.repository.relation_type_counts(),
            "recent_runs": [self._run_payload(run) for run in recent_runs],
        }

    def list_nodes(
        self,
        *,
        current_user: User,
        node_type: str | None = None,
        manufacturer: str | None = None,
        product_series: str | None = None,
        device_type: str | None = None,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        self._require_read(current_user)
        nodes, total = self.repository.list_nodes(
            node_type=node_type,
            manufacturer=manufacturer,
            product_series=product_series,
            device_type=device_type,
            status=status,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return self._page([self._node_payload(node) for node in nodes], total, page, page_size)

    def create_node(self, payload: KGNodeCreate, *, current_user: User) -> dict[str, Any]:
        self._require_manager(current_user)
        existing = self.repository.find_node(
            node_type=payload.node_type,
            canonical_name=payload.canonical_name,
            manufacturer=payload.manufacturer,
            product_series=payload.product_series,
            device_type=payload.device_type,
        )
        if existing:
            raise KnowledgeGraphServiceError("Knowledge graph node already exists")
        try:
            node = self.repository.create_node(
                KGNode(
                    node_type=payload.node_type,
                    canonical_name=payload.canonical_name.strip(),
                    display_name=payload.display_name or payload.canonical_name.strip(),
                    manufacturer=payload.manufacturer,
                    product_series=payload.product_series,
                    device_type=payload.device_type,
                    properties_json=payload.properties_json,
                    confidence=payload.confidence,
                    status=payload.status,
                    source_type=payload.source_type or "manual_graph",
                    source_id=payload.source_id,
                    created_by=current_user.id,
                )
            )
            self.repository.add_aliases(node.id, payload.aliases, source_type="manual_graph")
            self.db.commit()
            self.db.refresh(node)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise KnowledgeGraphServiceError(f"Create node failed: {exc}") from exc
        return self._node_payload(self.repository.get_node(node.id) or node)

    def get_node(self, node_id: UUID, *, current_user: User) -> dict[str, Any]:
        self._require_read(current_user)
        node = self.repository.get_node(node_id)
        if not node:
            raise KnowledgeGraphServiceError("Knowledge graph node not found")
        return self._node_payload(node)

    def update_node(self, node_id: UUID, payload: KGNodeUpdate, *, current_user: User) -> dict[str, Any]:
        self._require_manager(current_user)
        node = self.repository.get_node(node_id)
        if not node:
            raise KnowledgeGraphServiceError("Knowledge graph node not found")
        values = payload.model_dump(exclude_unset=True)
        try:
            for field in (
                "canonical_name",
                "display_name",
                "manufacturer",
                "product_series",
                "device_type",
                "properties_json",
                "confidence",
                "status",
            ):
                if field in values and values[field] is not None:
                    setattr(node, field, values[field])
            self.repository.update_node(node)
            if "aliases" in values and values["aliases"] is not None:
                self.repository.replace_aliases(node, values["aliases"], source_type="manual_graph")
            self.db.commit()
            self.db.refresh(node)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise KnowledgeGraphServiceError(f"Update node failed: {exc}") from exc
        return self._node_payload(self.repository.get_node(node.id) or node)

    def archive_node(self, node_id: UUID, *, current_user: User) -> dict[str, Any]:
        self._require_manager(current_user)
        node = self.repository.get_node(node_id)
        if not node:
            raise KnowledgeGraphServiceError("Knowledge graph node not found")
        try:
            node.status = "archived"
            self.repository.update_node(node)
            self.db.commit()
            self.db.refresh(node)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise KnowledgeGraphServiceError(f"Archive node failed: {exc}") from exc
        return self._node_payload(node)

    def merge_node(self, node_id: UUID, payload: KGNodeMergeRequest, *, current_user: User) -> dict[str, Any]:
        self._require_manager(current_user)
        source = self.repository.get_node(node_id)
        target = self.repository.get_node(payload.target_node_id)
        if not source or not target:
            raise KnowledgeGraphServiceError("Source or target node not found")
        if source.id == target.id:
            raise KnowledgeGraphServiceError("Source and target nodes must be different")
        try:
            related_edges, _ = self.repository.list_edges(source_node_id=source.id, page=1, page_size=1000)
            target_edges, _ = self.repository.list_edges(target_node_id=source.id, page=1, page_size=1000)
            for edge in related_edges + target_edges:
                new_source_id = target.id if edge.source_node_id == source.id else edge.source_node_id
                new_target_id = target.id if edge.target_node_id == source.id else edge.target_node_id
                if new_source_id == new_target_id:
                    edge.status = "archived"
                    self.repository.update_edge(edge)
                    continue
                duplicate = self.repository.find_edge(
                    source_node_id=new_source_id,
                    target_node_id=new_target_id,
                    relation_type=edge.relation_type,
                )
                if duplicate and duplicate.id != edge.id:
                    edge.status = "archived"
                else:
                    edge.source_node_id = new_source_id
                    edge.target_node_id = new_target_id
                self.repository.update_edge(edge)
            if payload.merge_alias:
                self.repository.add_aliases(target.id, [source.canonical_name, source.display_name or source.canonical_name], source_type="node_merge")
            if payload.archive_source:
                source.status = "archived"
                self.repository.update_node(source)
            self.db.commit()
            self.db.refresh(target)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise KnowledgeGraphServiceError(f"Merge node failed: {exc}") from exc
        return {"source": self._node_payload(source), "target": self._node_payload(self.repository.get_node(target.id) or target)}

    def list_edges(
        self,
        *,
        current_user: User,
        source_node_id: UUID | None = None,
        target_node_id: UUID | None = None,
        relation_type: str | None = None,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        self._require_read(current_user)
        edges, total = self.repository.list_edges(
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relation_type=relation_type,
            status=status,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return self._page([self._edge_payload(edge) for edge in edges], total, page, page_size)

    def create_edge(self, payload: KGEdgeCreate, *, current_user: User) -> dict[str, Any]:
        self._require_manager(current_user)
        if not self.repository.get_node(payload.source_node_id) or not self.repository.get_node(payload.target_node_id):
            raise KnowledgeGraphServiceError("Source or target node not found")
        if self.repository.find_edge(
            source_node_id=payload.source_node_id,
            target_node_id=payload.target_node_id,
            relation_type=payload.relation_type,
        ):
            raise KnowledgeGraphServiceError("Knowledge graph edge already exists")
        try:
            edge = self.repository.create_edge(
                KGEdge(
                    source_node_id=payload.source_node_id,
                    target_node_id=payload.target_node_id,
                    relation_type=payload.relation_type,
                    display_relation=payload.display_relation,
                    properties_json=payload.properties_json,
                    confidence=payload.confidence,
                    evidence_count=0,
                    status=payload.status,
                    source_type=payload.source_type or "manual_graph",
                    source_id=payload.source_id,
                    created_by=current_user.id,
                )
            )
            if payload.evidence_text:
                self.repository.create_evidence(
                    KGEvidenceLink(
                        edge_id=edge.id,
                        source_type="manual_graph",
                        source_id=edge.id,
                        evidence_text=payload.evidence_text,
                        confidence=payload.confidence,
                    )
                )
                edge.evidence_count = 1
                self.repository.update_edge(edge)
            self.db.commit()
            self.db.refresh(edge)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise KnowledgeGraphServiceError(f"Create edge failed: {exc}") from exc
        return self._edge_payload(self.repository.get_edge(edge.id) or edge)

    def get_edge(self, edge_id: UUID, *, current_user: User) -> dict[str, Any]:
        self._require_read(current_user)
        edge = self.repository.get_edge(edge_id)
        if not edge:
            raise KnowledgeGraphServiceError("Knowledge graph edge not found")
        return self._edge_payload(edge)

    def update_edge(self, edge_id: UUID, payload: KGEdgeUpdate, *, current_user: User) -> dict[str, Any]:
        self._require_manager(current_user)
        edge = self.repository.get_edge(edge_id)
        if not edge:
            raise KnowledgeGraphServiceError("Knowledge graph edge not found")
        values = payload.model_dump(exclude_unset=True)
        try:
            for field in ("relation_type", "display_relation", "properties_json", "confidence", "status"):
                if field in values and values[field] is not None:
                    setattr(edge, field, values[field])
            self.repository.update_edge(edge)
            self.db.commit()
            self.db.refresh(edge)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise KnowledgeGraphServiceError(f"Update edge failed: {exc}") from exc
        return self._edge_payload(self.repository.get_edge(edge.id) or edge)

    def archive_edge(self, edge_id: UUID, *, current_user: User) -> dict[str, Any]:
        self._require_manager(current_user)
        edge = self.repository.get_edge(edge_id)
        if not edge:
            raise KnowledgeGraphServiceError("Knowledge graph edge not found")
        try:
            edge.status = "archived"
            self.repository.update_edge(edge)
            self.db.commit()
            self.db.refresh(edge)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise KnowledgeGraphServiceError(f"Archive edge failed: {exc}") from exc
        return self._edge_payload(edge)

    def list_evidence(self, *, current_user: User, **kwargs: Any) -> dict[str, Any]:
        self._require_read(current_user)
        result = KGEvidenceService(self.db).list_evidence(**kwargs)
        return {
            **result,
            "items": [self._evidence_payload(item) for item in result["items"]],
        }

    def graph(
        self,
        *,
        current_user: User,
        node_type: str | None = None,
        relation_type: str | None = None,
        manufacturer: str | None = None,
        product_series: str | None = None,
        fault_type: str | None = None,
        keyword: str | None = None,
        limit: int = 80,
        depth: int = 1,
    ) -> dict[str, Any]:
        self._require_read(current_user)
        safe_limit = max(1, min(limit, 200))
        terms = self._business_terms(
            manufacturer=manufacturer,
            product_series=product_series,
            fault_type=fault_type,
            alarm_code=None,
            question=keyword,
        )
        graph_keyword = keyword or fault_type
        seed_nodes = self.repository.graph_nodes(
            node_type=node_type,
            manufacturer=manufacturer,
            product_series=product_series,
            device_type="pv_inverter",
            keyword=graph_keyword,
            limit=safe_limit,
        )
        if not seed_nodes and terms:
            seed_nodes = self.repository.search_active_nodes(
                keywords=terms,
                manufacturer=manufacturer,
                product_series=product_series,
                device_type="pv_inverter",
                limit=safe_limit,
            )
        seed_scope = self.production_scope.evaluate(node_ids=[node.id for node in seed_nodes])
        seed_nodes = [node for node in seed_nodes if node.id in seed_scope.eligible_node_ids]
        edges: list[KGEdge] = []
        node_ids = {node.id for node in seed_nodes}
        for node in seed_nodes[: min(len(seed_nodes), 20)]:
            edges.extend(self.repository.neighborhood_edges(node.id, depth=depth, limit=safe_limit))
        if not seed_nodes:
            edges = self.repository.graph_edges(relation_type=relation_type, keyword=keyword, limit=safe_limit)
        if relation_type:
            edges = [edge for edge in edges if edge.relation_type == relation_type]
        for edge in edges:
            if self._active_edge(edge):
                node_ids.add(edge.source_node_id)
                node_ids.add(edge.target_node_id)
        nodes = [self.repository.get_node(node_id) for node_id in node_ids]
        active_nodes = [node for node in nodes if node and node.status == "active"]
        scope = self.production_scope.evaluate(
            node_ids=[node.id for node in active_nodes],
            edge_ids=[edge.id for edge in self._unique_edges(edges)],
        )
        active_nodes = [node for node in active_nodes if node.id in scope.eligible_node_ids]
        active_node_ids = {node.id for node in active_nodes}
        active_edges = [
            edge
            for edge in self._unique_edges(edges)
            if self._active_edge(edge)
            and edge.id in scope.eligible_edge_ids
            and edge.source_node_id in active_node_ids
            and edge.target_node_id in active_node_ids
        ][:safe_limit]
        active_nodes = active_nodes[:safe_limit]
        return {
            "nodes": [self._graph_node_payload(node, scope=scope) for node in active_nodes],
            "edges": [self._graph_edge_payload(edge, scope=scope) for edge in active_edges],
            "statistics": {
                "node_count": len(active_nodes),
                "edge_count": len(active_edges),
                "filter": {
                    "node_type": node_type,
                    "relation_type": relation_type,
                    "manufacturer": manufacturer,
                    "product_series": product_series,
                    "fault_type": fault_type,
                    "keyword": keyword,
                    "depth": depth,
                },
            },
            "legend": {"node_types": NODE_LEGEND, "relation_types": RELATION_LEGEND},
        }

    def search(
        self,
        *,
        current_user: User,
        keyword: str | None,
        manufacturer: str | None = None,
        product_series: str | None = None,
        node_type: str | None = None,
        relation_type: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        self._require_read(current_user)
        safe_limit = max(1, min(limit, 50))
        terms = self._extract_terms(keyword or "")
        nodes = self.repository.search_active_nodes(
            keywords=terms,
            manufacturer=manufacturer,
            product_series=product_series,
            device_type="pv_inverter",
            node_types={node_type} if node_type else None,
            limit=safe_limit,
        )
        edges = self.repository.search_active_edges(keywords=terms, relation_type=relation_type, limit=safe_limit)
        if relation_type:
            edges = [edge for edge in edges if edge.relation_type == relation_type]
        scope = self.production_scope.evaluate(
            node_ids=[node.id for node in nodes],
            edge_ids=[edge.id for edge in edges],
        )
        nodes = [node for node in nodes if node.status == "active" and node.id in scope.eligible_node_ids]
        node_ids = {node.id for node in nodes}
        edges = [
            edge
            for edge in edges
            if self._active_edge(edge)
            and edge.id in scope.eligible_edge_ids
            and edge.source_node_id in node_ids
            and edge.target_node_id in node_ids
        ]
        evidence = self._collect_evidence(nodes, edges, limit=12, scope=scope)
        return {
            "keyword": keyword,
            "nodes": [self._production_node_payload(node, scope) for node in nodes],
            "edges": [self._production_edge_payload(edge, scope) for edge in edges],
            "evidence": evidence,
        }

    def business_context(
        self,
        *,
        current_user: User | None = None,
        device_id: UUID | None = None,
        manufacturer: str | None = None,
        product_series: str | None = None,
        fault_type: str | None = None,
        alarm_code: str | None = None,
        question: str | None = None,
        diagnosis_trace_id: str | None = None,
        sop_template_id: UUID | None = None,
        task_id: UUID | None = None,
        limit: int = 30,
    ) -> dict[str, Any]:
        if current_user is not None:
            self._require_read(current_user)
        safe_limit = max(1, min(limit, 80))
        terms = self._business_terms(
            manufacturer=manufacturer,
            product_series=product_series,
            fault_type=fault_type,
            alarm_code=alarm_code,
            question=question,
        )
        matched_nodes = self.repository.search_active_nodes(
            keywords=terms,
            manufacturer=manufacturer,
            product_series=product_series,
            device_type="pv_inverter",
            limit=safe_limit,
        )
        if not matched_nodes and (fault_type or alarm_code):
            matched_nodes = self.repository.search_active_nodes(
                keywords=[term for term in [fault_type, alarm_code] if term],
                device_type="pv_inverter",
                limit=safe_limit,
            )
        matched_scope = self.production_scope.evaluate(node_ids=[node.id for node in matched_nodes])
        matched_nodes = [node for node in matched_nodes if node.id in matched_scope.eligible_node_ids]

        edges: list[KGEdge] = []
        for node in matched_nodes[:20]:
            edges.extend(self.repository.neighborhood_edges(node.id, depth=2, limit=100))
        edges = [edge for edge in self._unique_edges(edges) if self._active_edge(edge)]
        active_node_ids = {node.id for node in matched_nodes if node.status == "active"}
        for edge in edges:
            active_node_ids.add(edge.source_node_id)
            active_node_ids.add(edge.target_node_id)
        nodes = [self.repository.get_node(node_id) for node_id in active_node_ids]
        active_nodes = [node for node in nodes if node and node.status == "active"]
        scope = self.production_scope.evaluate(
            node_ids=[node.id for node in active_nodes],
            edge_ids=[edge.id for edge in edges],
        )
        active_nodes = [node for node in active_nodes if node.id in scope.eligible_node_ids]
        active_node_ids = {node.id for node in active_nodes}
        edges = [
            edge
            for edge in edges
            if edge.id in scope.eligible_edge_ids
            and edge.source_node_id in active_node_ids
            and edge.target_node_id in active_node_ids
        ]

        grouped = self._group_business_nodes(matched_nodes, active_nodes, edges, scope=scope)
        evidence = self._collect_evidence(active_nodes, edges, limit=20, scope=scope)
        graph_paths = self._business_paths(matched_nodes, grouped, edges, scope=scope)
        summary = {
            "enabled": True,
            "matched_node_count": len([node for node in matched_nodes if node.status == "active"]),
            "edge_count": len(edges),
            "evidence_count": len(evidence),
            "device_id": str(device_id) if device_id else None,
            "diagnosis_trace_id": diagnosis_trace_id,
            "sop_template_id": str(sop_template_id) if sop_template_id else None,
            "task_id": str(task_id) if task_id else None,
            "terms": terms[:20],
            "boundary": "Only active knowledge graph nodes, active relations, and traceable evidence are used.",
        }
        return {
            "matched_nodes": [self._production_node_payload(node, scope) for node in matched_nodes if node.status == "active"],
            "related_faults": grouped["related_faults"],
            "related_alarms": grouped["related_alarms"],
            "related_causes": grouped["related_causes"],
            "inspection_items": grouped["inspection_items"],
            "recommended_actions": grouped["recommended_actions"],
            "safety_risks": grouped["safety_risks"],
            "related_sop": grouped["related_sop"],
            "tools": grouped["tools"],
            "parts": grouped["parts"],
            "evidence": evidence,
            "graph_paths": graph_paths,
            "kg_nodes": [self._production_node_payload(node, scope) for node in active_nodes],
            "kg_edges": [self._production_edge_payload(edge, scope) for edge in edges],
            "summary": summary,
        }

    def create_evidence(self, payload: KGEvidenceCreate, *, current_user: User) -> dict[str, Any]:
        self._require_manager(current_user)
        try:
            evidence = KGEvidenceService(self.db).create_evidence(payload)
            self.db.commit()
            self.db.refresh(evidence)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise KnowledgeGraphServiceError(f"Create evidence failed: {exc}") from exc
        return self._evidence_payload(evidence)

    def neighborhood(self, node_id: UUID, *, current_user: User, depth: int = 1) -> dict[str, Any]:
        self._require_read(current_user)
        center = self.repository.get_node(node_id)
        if not center:
            raise KnowledgeGraphServiceError("Knowledge graph node not found")
        edges = self.repository.neighborhood_edges(node_id, depth=depth)
        node_ids = {node_id}
        for edge in edges:
            node_ids.add(edge.source_node_id)
            node_ids.add(edge.target_node_id)
        nodes = [self.repository.get_node(item) for item in node_ids]
        return {
            "center": self._node_payload(center),
            "nodes": [self._node_payload(node) for node in nodes if node],
            "edges": [self._edge_payload(edge) for edge in edges],
        }

    def path(
        self,
        *,
        current_user: User,
        source_node_id: UUID,
        target_node_id: UUID,
        max_depth: int = 3,
    ) -> dict[str, Any]:
        self._require_read(current_user)
        if not self.repository.get_node(source_node_id) or not self.repository.get_node(target_node_id):
            raise KnowledgeGraphServiceError("Source or target node not found")
        queue = deque([(source_node_id, [], [])])
        visited = {source_node_id}
        while queue:
            current_id, node_path, edge_path = queue.popleft()
            if len(edge_path) >= max_depth:
                continue
            outgoing, _ = self.repository.list_edges(source_node_id=current_id, status="active", page=1, page_size=1000)
            incoming, _ = self.repository.list_edges(target_node_id=current_id, status="active", page=1, page_size=1000)
            for edge in outgoing + incoming:
                next_id = edge.target_node_id if edge.source_node_id == current_id else edge.source_node_id
                if next_id in visited:
                    continue
                next_nodes = [*node_path, current_id]
                next_edges = [*edge_path, edge.id]
                if next_id == target_node_id:
                    all_node_ids = [*next_nodes, next_id]
                    return {
                        "found": True,
                        "nodes": [self._node_payload(self.repository.get_node(node_id)) for node_id in all_node_ids if self.repository.get_node(node_id)],
                        "edges": [self._edge_payload(self.repository.get_edge(edge_id)) for edge_id in next_edges if self.repository.get_edge(edge_id)],
                    }
                visited.add(next_id)
                queue.append((next_id, next_nodes, next_edges))
        return {"found": False, "nodes": [], "edges": []}

    def extract_from_document(self, document_id: UUID, payload: KGExtractionRequest, *, current_user: User) -> dict[str, Any]:
        return self._serialize_extraction(
            KGExtractionService(self.db).extract_from_document(
                document_id,
                current_user=current_user,
                max_chunks=payload.max_chunks,
            )
        )

    def extract_from_contribution(self, contribution_id: UUID, payload: KGExtractionRequest, *, current_user: User) -> dict[str, Any]:
        return self._serialize_extraction(
            KGExtractionService(self.db).extract_from_contribution(
                contribution_id,
                current_user=current_user,
            )
        )

    def extract_from_record(
        self,
        record_type: str,
        record_id: UUID,
        payload: KGExtractionRequest,
        *,
        current_user: User,
    ) -> dict[str, Any]:
        return self._serialize_extraction(
            KGExtractionService(self.db).extract_from_record(
                record_type,
                record_id,
                current_user=current_user,
            )
        )

    def list_runs(self, *, current_user: User, source_type: str | None = None, status: str | None = None, page: int = 1, page_size: int = 20) -> dict[str, Any]:
        self._require_read(current_user)
        runs, total = self.repository.list_runs(source_type=source_type, status=status, page=page, page_size=page_size)
        return self._page([self._run_payload(run) for run in runs], total, page, page_size)

    def get_run(self, run_id: UUID, *, current_user: User) -> dict[str, Any]:
        self._require_read(current_user)
        run = self.repository.get_run(run_id)
        if not run:
            raise KnowledgeGraphServiceError("Knowledge graph extraction run not found")
        return {
            **self._run_payload(run),
            "candidates": [self._candidate_payload(candidate) for candidate in run.candidates],
        }

    def list_candidates(self, *, current_user: User, run_id: UUID | None = None, candidate_type: str | None = None, status: str | None = None, page: int = 1, page_size: int = 20) -> dict[str, Any]:
        self._require_read(current_user)
        candidates, total = self.repository.list_candidates(
            run_id=run_id,
            candidate_type=candidate_type,
            status=status,
            page=page,
            page_size=page_size,
        )
        return self._page([self._candidate_payload(candidate) for candidate in candidates], total, page, page_size)

    def get_candidate(self, candidate_id: UUID, *, current_user: User) -> dict[str, Any]:
        self._require_read(current_user)
        candidate = self.repository.get_candidate(candidate_id)
        if not candidate:
            raise KnowledgeGraphServiceError("Knowledge graph candidate not found")
        return self._candidate_payload(candidate)

    def approve_candidate(self, candidate_id: UUID, *, current_user: User, comment: str | None = None) -> dict[str, Any]:
        try:
            return KGCandidateService(self.db).approve(candidate_id, current_user=current_user, comment=comment)
        except KGCandidatePermissionError as exc:
            raise KnowledgeGraphPermissionError(str(exc)) from exc
        except KGCandidateServiceError as exc:
            raise KnowledgeGraphServiceError(str(exc)) from exc

    def reject_candidate(self, candidate_id: UUID, *, current_user: User, comment: str | None = None) -> dict[str, Any]:
        try:
            return KGCandidateService(self.db).reject(candidate_id, current_user=current_user, comment=comment)
        except KGCandidatePermissionError as exc:
            raise KnowledgeGraphPermissionError(str(exc)) from exc
        except KGCandidateServiceError as exc:
            raise KnowledgeGraphServiceError(str(exc)) from exc

    @staticmethod
    def _page(items: list[dict[str, Any]], total: int, page: int, page_size: int) -> dict[str, Any]:
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def _graph_node_payload(
        self,
        node: KGNode,
        *,
        scope: ProductionScopeEvaluation | None = None,
    ) -> dict[str, Any]:
        payload = self._production_node_payload(node, scope) if scope else self._node_payload(node)
        return {
            "id": payload["id"],
            "node_type": payload["node_type"],
            "display_name": payload["display_name"] or payload["canonical_name"],
            "canonical_name": payload["canonical_name"],
            "status": payload["status"],
            "confidence": payload["confidence"],
            "properties": payload["properties_json"],
            "evidence_count": payload["evidence_count"],
            "manufacturer": payload["manufacturer"],
            "product_series": payload["product_series"],
            "device_type": payload["device_type"],
            "evidence_ids": payload.get("evidence_ids", []),
        }

    def _graph_edge_payload(
        self,
        edge: KGEdge,
        *,
        scope: ProductionScopeEvaluation | None = None,
    ) -> dict[str, Any]:
        payload = self._production_edge_payload(edge, scope) if scope else self._edge_payload(edge)
        return {
            "id": payload["id"],
            "source_node_id": payload["source_node_id"],
            "target_node_id": payload["target_node_id"],
            "source_node_name": payload["source_node_name"],
            "target_node_name": payload["target_node_name"],
            "relation_type": payload["relation_type"],
            "display_relation": payload["display_relation"] or RELATION_LEGEND.get(payload["relation_type"], payload["relation_type"]),
            "confidence": payload["confidence"],
            "evidence_count": payload["evidence_count"],
            "status": payload["status"],
            "evidence_ids": payload.get("evidence_ids", []),
        }

    def _business_terms(
        self,
        *,
        manufacturer: str | None,
        product_series: str | None,
        fault_type: str | None,
        alarm_code: str | None,
        question: str | None,
    ) -> list[str]:
        terms: list[str] = []
        for value in [manufacturer, product_series, fault_type, alarm_code, question]:
            terms.extend(self._extract_terms(value or ""))
        if manufacturer == "huawei":
            terms.extend(["华为", "Huawei", "SUN2000", "FusionSolar"])
        if manufacturer == "sungrow":
            terms.extend(["阳光电源", "Sungrow", "SG"])
        if product_series:
            terms.append(product_series)
        if fault_type:
            terms.extend(FAULT_TYPE_TERMS.get(fault_type, [fault_type]))
        if alarm_code:
            terms.extend([alarm_code, alarm_code.upper()])
        return self._unique_texts(terms)[:60]

    def _extract_terms(self, text: str) -> list[str]:
        if not text:
            return []
        terms = [text.strip()] if text.strip() else []
        compact = re.sub(r"\s+", "", text)
        for term in DOMAIN_TERMS:
            if term.lower() in text.lower():
                terms.append(term)
        terms.extend(re.findall(r"[A-Za-z][A-Za-z0-9_.-]{1,32}", text))
        terms.extend(re.findall(r"(?:ALM-|A-)?\d{3,6}", text, flags=re.IGNORECASE))
        chinese_segments = re.findall(r"[\u4e00-\u9fff]{2,12}", compact)
        terms.extend(chinese_segments)
        for segment in chinese_segments:
            if len(segment) > 4:
                terms.extend(segment[index : index + 4] for index in range(0, len(segment) - 3, 2))
        return self._unique_texts(terms)

    def _group_business_nodes(
        self,
        matched_nodes: list[KGNode],
        active_nodes: list[KGNode],
        edges: list[KGEdge],
        *,
        scope: ProductionScopeEvaluation,
    ) -> dict[str, list[dict[str, Any]]]:
        by_id = {node.id: node for node in active_nodes}
        matched_ids = {node.id for node in matched_nodes if node.status == "active"}
        grouped: dict[str, list[dict[str, Any]]] = {
            "related_faults": [],
            "related_alarms": [],
            "related_causes": [],
            "inspection_items": [],
            "recommended_actions": [],
            "safety_risks": [],
            "related_sop": [],
            "tools": [],
            "parts": [],
        }

        def add(group: str, node: KGNode | None, edge: KGEdge | None = None) -> None:
            if not node or node.status != "active":
                return
            entry = self._business_node_entry(node, edge, scope=scope)
            if not any(item["id"] == entry["id"] for item in grouped[group]):
                grouped[group].append(entry)

        for node in active_nodes:
            if node.node_type == "fault":
                add("related_faults", node)
            elif node.node_type == "alarm":
                add("related_alarms", node)
            elif node.node_type == "cause":
                add("related_causes", node)
            elif node.node_type in {"inspection_item", "component", "symptom"}:
                add("inspection_items", node)
            elif node.node_type == "action":
                add("recommended_actions", node)
            elif node.node_type == "safety_risk":
                add("safety_risks", node)
            elif node.node_type in {"sop_template", "sop_step"}:
                add("related_sop", node)
            elif node.node_type == "tool":
                add("tools", node)
            elif node.node_type == "part":
                add("parts", node)

        for edge in edges:
            source = by_id.get(edge.source_node_id)
            target = by_id.get(edge.target_node_id)
            if not source or not target:
                continue
            candidate = target if edge.source_node_id in matched_ids else source
            if edge.relation_type == "CAUSED_BY":
                add("related_causes", candidate if candidate.node_type == "cause" else target, edge)
            elif edge.relation_type in {"CHECK_BY", "HAS_SYMPTOM"}:
                add("inspection_items", candidate, edge)
            elif edge.relation_type == "RESOLVED_BY":
                add("recommended_actions", candidate if candidate.node_type == "action" else target, edge)
            elif edge.relation_type == "HAS_SAFETY_RISK":
                add("safety_risks", candidate if candidate.node_type == "safety_risk" else target, edge)
            elif edge.relation_type == "USES_TOOL":
                add("tools", candidate if candidate.node_type == "tool" else target, edge)
            elif edge.relation_type == "REQUIRES_PART":
                add("parts", candidate if candidate.node_type == "part" else target, edge)
            elif edge.relation_type in {"GUIDED_BY_SOP", "HAS_STEP"}:
                add("related_sop", candidate, edge)
            elif edge.relation_type == "HAS_ALARM":
                add("related_alarms", candidate if candidate.node_type == "alarm" else target, edge)

        return {key: value[:10] for key, value in grouped.items()}

    def _business_node_entry(
        self,
        node: KGNode,
        edge: KGEdge | None = None,
        *,
        scope: ProductionScopeEvaluation,
    ) -> dict[str, Any]:
        node_evidence_ids = scope.evidence_ids_for_node(node.id)
        edge_evidence_ids = scope.evidence_ids_for_edge(edge.id) if edge else []
        return {
            "id": str(node.id),
            "node_type": node.node_type,
            "display_name": node.display_name or node.canonical_name,
            "canonical_name": node.canonical_name,
            "manufacturer": node.manufacturer,
            "product_series": node.product_series,
            "device_type": node.device_type,
            "confidence": node.confidence,
            "evidence_count": len(node_evidence_ids),
            "evidence_ids": node_evidence_ids,
            "via_edge_id": str(edge.id) if edge else None,
            "via_evidence_ids": edge_evidence_ids,
            "via_relation": edge.relation_type if edge else None,
            "via_relation_label": RELATION_LEGEND.get(edge.relation_type, edge.relation_type) if edge else None,
        }

    def _collect_evidence(
        self,
        nodes: list[KGNode],
        edges: list[KGEdge],
        *,
        limit: int = 20,
        scope: ProductionScopeEvaluation | None = None,
    ) -> list[dict[str, Any]]:
        if scope is None:
            scope = self.production_scope.evaluate(
                node_ids=[node.id for node in nodes],
                edge_ids=[edge.id for edge in edges],
            )
        return scope.all_evidence(limit=limit)

    def _collect_all_evidence_for_audit(self, nodes: list[KGNode], edges: list[KGEdge], *, limit: int = 20) -> list[dict[str, Any]]:
        """Legacy unscoped expansion retained only for explicit administrative audits."""
        evidence_items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for node in nodes[:20]:
            items, _ = self.repository.list_evidence(node_id=node.id, page=1, page_size=3)
            for item in items:
                self._append_unique_evidence(evidence_items, seen, item, limit)
                if len(evidence_items) >= limit:
                    return evidence_items
        for edge in edges[:20]:
            items, _ = self.repository.list_evidence(edge_id=edge.id, page=1, page_size=3)
            for item in items:
                self._append_unique_evidence(evidence_items, seen, item, limit)
                if len(evidence_items) >= limit:
                    return evidence_items
        return evidence_items

    def _append_unique_evidence(
        self,
        evidence_items: list[dict[str, Any]],
        seen: set[str],
        item: KGEvidenceLink,
        limit: int,
    ) -> None:
        if len(evidence_items) >= limit:
            return
        key = str(item.id)
        if key in seen:
            return
        seen.add(key)
        evidence_items.append(self._evidence_payload(item))

    def _business_paths(
        self,
        matched_nodes: list[KGNode],
        grouped: dict[str, list[dict[str, Any]]],
        edges: list[KGEdge],
        *,
        scope: ProductionScopeEvaluation,
    ) -> list[dict[str, Any]]:
        matched_ids = {node.id for node in matched_nodes if node.status == "active"}
        target_ids = {
            UUID(item["id"])
            for group in grouped.values()
            for item in group
            if item.get("id")
        }
        paths: list[dict[str, Any]] = []
        for edge in edges:
            if edge.source_node_id in matched_ids or edge.target_node_id in matched_ids:
                source = getattr(edge, "source_node", None) or self.repository.get_node(edge.source_node_id)
                target = getattr(edge, "target_node", None) or self.repository.get_node(edge.target_node_id)
                if not source or not target:
                    continue
                if edge.source_node_id not in target_ids and edge.target_node_id not in target_ids:
                    continue
                paths.append(
                    {
                        "nodes": [
                            self._production_node_payload(source, scope),
                            self._production_node_payload(target, scope),
                        ],
                        "edges": [self._production_edge_payload(edge, scope)],
                        "summary": (
                            f"{source.display_name or source.canonical_name} "
                            f"{RELATION_LEGEND.get(edge.relation_type, edge.relation_type)} "
                            f"{target.display_name or target.canonical_name}"
                        ),
                    }
                )
            if len(paths) >= 8:
                break
        return paths

    @staticmethod
    def _active_edge(edge: KGEdge) -> bool:
        source = getattr(edge, "source_node", None)
        target = getattr(edge, "target_node", None)
        return (
            edge.status == "active"
            and (source is None or source.status == "active")
            and (target is None or target.status == "active")
        )

    @staticmethod
    def _unique_edges(edges: list[KGEdge]) -> list[KGEdge]:
        unique: dict[UUID, KGEdge] = {}
        for edge in edges:
            unique[edge.id] = edge
        return list(unique.values())

    @staticmethod
    def _unique_texts(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            cleaned = str(value or "").strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(cleaned)
        return result

    @staticmethod
    def _require_read(current_user: User) -> None:
        if current_user.role not in READ_ROLES:
            raise KnowledgeGraphPermissionError("Permission denied")

    @staticmethod
    def _require_manager(current_user: User) -> None:
        if current_user.role not in MANAGER_ROLES:
            raise KnowledgeGraphPermissionError("Only experts and admins can manage knowledge graph data")

    def _serialize_extraction(self, result: dict[str, Any]) -> dict[str, Any]:
        return {
            "run": self._run_payload(result["run"]),
            "candidates": [self._candidate_payload(candidate) for candidate in result["candidates"]],
        }

    def _production_node_payload(
        self,
        node: KGNode,
        scope: ProductionScopeEvaluation,
    ) -> dict[str, Any]:
        payload = self._node_payload(node)
        evidence_ids = scope.evidence_ids_for_node(node.id)
        payload["evidence_count"] = len(evidence_ids)
        payload["evidence_ids"] = evidence_ids
        payload["grounding_status"] = "GROUNDED_CURRENT" if evidence_ids else "UNSUPPORTED_CURRENT_SOURCE"
        payload["production_grounding_status"] = "CURRENT_VALID" if evidence_ids else "UNSUPPORTED_CURRENT_SOURCE"
        return payload

    def _production_edge_payload(
        self,
        edge: KGEdge,
        scope: ProductionScopeEvaluation,
    ) -> dict[str, Any]:
        payload = self._edge_payload(edge)
        evidence_ids = scope.evidence_ids_for_edge(edge.id)
        payload["evidence_count"] = len(evidence_ids)
        payload["evidence_ids"] = evidence_ids
        payload["grounding_status"] = "GROUNDED_CURRENT" if evidence_ids else "UNSUPPORTED_CURRENT_SOURCE"
        payload["production_grounding_status"] = "CURRENT_VALID" if evidence_ids else "UNSUPPORTED_CURRENT_SOURCE"
        return payload

    def _node_payload(self, node: KGNode | None) -> dict[str, Any]:
        if node is None:
            return {}
        return {
            "id": str(node.id),
            "node_type": node.node_type,
            "canonical_name": node.canonical_name,
            "display_name": node.display_name,
            "manufacturer": node.manufacturer,
            "product_series": node.product_series,
            "device_type": node.device_type,
            "properties_json": node.properties_json or {},
            "confidence": node.confidence,
            "status": node.status,
            "source_type": node.source_type,
            "source_id": str(node.source_id) if node.source_id else None,
            "created_by": str(node.created_by) if node.created_by else None,
            "aliases": [alias.alias for alias in getattr(node, "aliases", [])],
            "evidence_count": len(getattr(node, "evidence_links", []) or []),
            "created_at": node.created_at,
            "updated_at": node.updated_at,
        }

    def _edge_payload(self, edge: KGEdge | None) -> dict[str, Any]:
        if edge is None:
            return {}
        source_node = getattr(edge, "source_node", None)
        target_node = getattr(edge, "target_node", None)
        return {
            "id": str(edge.id),
            "source_node_id": str(edge.source_node_id),
            "target_node_id": str(edge.target_node_id),
            "source_node_name": getattr(source_node, "display_name", None) or getattr(source_node, "canonical_name", None),
            "target_node_name": getattr(target_node, "display_name", None) or getattr(target_node, "canonical_name", None),
            "relation_type": edge.relation_type,
            "display_relation": edge.display_relation,
            "properties_json": edge.properties_json or {},
            "confidence": edge.confidence,
            "evidence_count": edge.evidence_count,
            "status": edge.status,
            "source_type": edge.source_type,
            "source_id": str(edge.source_id) if edge.source_id else None,
            "created_by": str(edge.created_by) if edge.created_by else None,
            "created_at": edge.created_at,
            "updated_at": edge.updated_at,
        }

    @staticmethod
    def _evidence_payload(evidence: KGEvidenceLink) -> dict[str, Any]:
        return {
            "id": str(evidence.id),
            "node_id": str(evidence.node_id) if evidence.node_id else None,
            "edge_id": str(evidence.edge_id) if evidence.edge_id else None,
            "source_type": evidence.source_type,
            "source_id": str(evidence.source_id) if evidence.source_id else None,
            "document_id": str(evidence.document_id) if evidence.document_id else None,
            "chunk_id": str(evidence.chunk_id) if evidence.chunk_id else None,
            "contribution_id": str(evidence.contribution_id) if evidence.contribution_id else None,
            "diagnosis_trace_id": evidence.diagnosis_trace_id,
            "task_id": str(evidence.task_id) if evidence.task_id else None,
            "maintenance_record_id": str(evidence.maintenance_record_id) if evidence.maintenance_record_id else None,
            "media_id": str(evidence.media_id) if evidence.media_id else None,
            "evidence_text": evidence.evidence_text,
            "confidence": evidence.confidence,
            "created_at": evidence.created_at,
        }

    @staticmethod
    def _run_payload(run) -> dict[str, Any]:
        return {
            "id": str(run.id),
            "source_type": run.source_type,
            "source_id": str(run.source_id) if run.source_id else None,
            "extractor": run.extractor,
            "status": run.status,
            "candidate_count": run.candidate_count,
            "approved_count": run.approved_count,
            "rejected_count": run.rejected_count,
            "error_summary": run.error_summary,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "created_by": str(run.created_by) if run.created_by else None,
            "metadata_json": run.metadata_json,
            "created_at": run.created_at,
        }

    @staticmethod
    def _candidate_payload(candidate) -> dict[str, Any]:
        return {
            "id": str(candidate.id),
            "run_id": str(candidate.run_id),
            "candidate_type": candidate.candidate_type,
            "payload_json": candidate.payload_json,
            "status": candidate.status,
            "confidence": candidate.confidence,
            "evidence_text": candidate.evidence_text,
            "approved_node_id": str(candidate.approved_node_id) if candidate.approved_node_id else None,
            "approved_edge_id": str(candidate.approved_edge_id) if candidate.approved_edge_id else None,
            "reviewed_by": str(candidate.reviewed_by) if candidate.reviewed_by else None,
            "reviewed_at": candidate.reviewed_at,
            "review_comment": candidate.review_comment,
            "created_at": candidate.created_at,
        }
