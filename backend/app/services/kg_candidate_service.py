from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import KGCandidate, KGEdge, KGEvidenceLink, KGNode, User
from app.repositories.knowledge_graph_repository import KnowledgeGraphRepository


class KGCandidateServiceError(ValueError):
    pass


class KGCandidatePermissionError(PermissionError):
    pass


REVIEWER_ROLES = {"admin", "expert"}


class KGCandidateService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = KnowledgeGraphRepository(db)

    def approve(self, candidate_id: UUID, *, current_user: User, comment: str | None = None) -> dict[str, Any]:
        self._require_reviewer(current_user)
        candidate = self._get_pending(candidate_id)
        try:
            if candidate.candidate_type == "node":
                node = self._approve_node_candidate(candidate, current_user=current_user)
                candidate.approved_node_id = node.id
            elif candidate.candidate_type == "edge":
                edge = self._approve_edge_candidate(candidate, current_user=current_user)
                candidate.approved_edge_id = edge.id
            elif candidate.candidate_type == "alias":
                node = self._approve_alias_candidate(candidate)
                candidate.approved_node_id = node.id
            else:
                raise KGCandidateServiceError("Unsupported candidate type")

            candidate.status = "approved"
            candidate.reviewed_by = current_user.id
            candidate.reviewed_at = datetime.now(timezone.utc)
            candidate.review_comment = comment
            self.repository.update_candidate(candidate)
            self._refresh_run_counts(candidate.run_id)
            self.db.commit()
            self.db.refresh(candidate)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise KGCandidateServiceError(f"Candidate approval failed: {exc}") from exc
        return self._serialize_candidate(candidate)

    def reject(self, candidate_id: UUID, *, current_user: User, comment: str | None = None) -> dict[str, Any]:
        self._require_reviewer(current_user)
        candidate = self._get_pending(candidate_id)
        try:
            candidate.status = "rejected"
            candidate.reviewed_by = current_user.id
            candidate.reviewed_at = datetime.now(timezone.utc)
            candidate.review_comment = comment
            self.repository.update_candidate(candidate)
            self._refresh_run_counts(candidate.run_id)
            self.db.commit()
            self.db.refresh(candidate)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise KGCandidateServiceError(f"Candidate rejection failed: {exc}") from exc
        return self._serialize_candidate(candidate)

    def _approve_node_candidate(self, candidate: KGCandidate, *, current_user: User) -> KGNode:
        payload = candidate.payload_json or {}
        node = self._ensure_node(payload, current_user=current_user, confidence=candidate.confidence)
        self._create_evidence_from_payload(payload, node_id=node.id, confidence=candidate.confidence)
        return node

    def _approve_edge_candidate(self, candidate: KGCandidate, *, current_user: User) -> KGEdge:
        payload = candidate.payload_json or {}
        source_payload = payload.get("source_node") or {}
        target_payload = payload.get("target_node") or {}
        if not source_payload or not target_payload:
            raise KGCandidateServiceError("Edge candidate is missing source or target node")
        source_node = self._ensure_node(source_payload, current_user=current_user, confidence=candidate.confidence)
        target_node = self._ensure_node(target_payload, current_user=current_user, confidence=candidate.confidence)
        relation_type = payload.get("relation_type")
        if not relation_type:
            raise KGCandidateServiceError("Edge candidate is missing relation_type")
        edge = self.repository.find_edge(
            source_node_id=source_node.id,
            target_node_id=target_node.id,
            relation_type=relation_type,
        )
        if not edge:
            edge = self.repository.create_edge(
                KGEdge(
                    source_node_id=source_node.id,
                    target_node_id=target_node.id,
                    relation_type=relation_type,
                    display_relation=payload.get("display_relation"),
                    properties_json=payload.get("properties_json") or {},
                    confidence=max(0.0, min(1.0, float(candidate.confidence or 0.6))),
                    evidence_count=0,
                    status="active",
                    source_type=payload.get("source_type"),
                    source_id=self._uuid_or_none(payload.get("source_id")),
                    created_by=current_user.id,
                )
            )
        else:
            edge.status = "active"
            edge.confidence = max(float(edge.confidence or 0.0), float(candidate.confidence or 0.6))
            if payload.get("display_relation"):
                edge.display_relation = payload.get("display_relation")
            edge = self.repository.update_edge(edge)
        evidence = self._create_evidence_from_payload(payload, edge_id=edge.id, confidence=candidate.confidence)
        if evidence:
            edge.evidence_count = (edge.evidence_count or 0) + 1
            self.repository.update_edge(edge)
        return edge

    def _approve_alias_candidate(self, candidate: KGCandidate) -> KGNode:
        payload = candidate.payload_json or {}
        node_id = self._uuid_or_none(payload.get("node_id"))
        alias = str(payload.get("alias") or "").strip()
        if not node_id or not alias:
            raise KGCandidateServiceError("Alias candidate requires node_id and alias")
        node = self.repository.get_node(node_id)
        if not node:
            raise KGCandidateServiceError("Alias candidate node does not exist")
        self.repository.add_aliases(node.id, [alias], source_type=payload.get("source_type"))
        return node

    def _ensure_node(self, payload: dict[str, Any], *, current_user: User, confidence: float) -> KGNode:
        node_type = payload.get("node_type")
        canonical_name = payload.get("canonical_name")
        if not node_type or not canonical_name:
            raise KGCandidateServiceError("Node payload is missing node_type or canonical_name")
        device_type = payload.get("device_type") or "pv_inverter"
        node = self.repository.find_node(
            node_type=node_type,
            canonical_name=canonical_name,
            manufacturer=payload.get("manufacturer"),
            product_series=payload.get("product_series"),
            device_type=device_type,
        )
        if not node:
            node = self.repository.create_node(
                KGNode(
                    node_type=node_type,
                    canonical_name=canonical_name,
                    display_name=payload.get("display_name") or canonical_name,
                    manufacturer=payload.get("manufacturer"),
                    product_series=payload.get("product_series"),
                    device_type=device_type,
                    properties_json=payload.get("properties_json") or {},
                    confidence=max(0.0, min(1.0, float(confidence or 0.6))),
                    status="active",
                    source_type=payload.get("source_type"),
                    source_id=self._uuid_or_none(payload.get("source_id")),
                    created_by=current_user.id,
                )
            )
        else:
            node.status = "active"
            node.confidence = max(float(node.confidence or 0.0), float(confidence or 0.6))
            if payload.get("display_name"):
                node.display_name = payload.get("display_name")
            node = self.repository.update_node(node)
        self.repository.add_aliases(node.id, payload.get("aliases") or [], source_type=payload.get("source_type"))
        return node

    def _create_evidence_from_payload(
        self,
        payload: dict[str, Any],
        *,
        node_id: UUID | None = None,
        edge_id: UUID | None = None,
        confidence: float,
    ) -> KGEvidenceLink | None:
        evidence = payload.get("evidence") or {}
        evidence_text = evidence.get("evidence_text") or payload.get("evidence_text")
        if not evidence_text:
            return None
        return self.repository.create_evidence(
            KGEvidenceLink(
                node_id=node_id,
                edge_id=edge_id,
                source_type=evidence.get("source_type") or payload.get("source_type") or "kg_extraction",
                source_id=self._uuid_or_none(evidence.get("source_id") or payload.get("source_id")),
                document_id=self._uuid_or_none(evidence.get("document_id")),
                chunk_id=self._uuid_or_none(evidence.get("chunk_id")),
                contribution_id=self._uuid_or_none(evidence.get("contribution_id")),
                diagnosis_trace_id=evidence.get("diagnosis_trace_id"),
                task_id=self._uuid_or_none(evidence.get("task_id")),
                maintenance_record_id=self._uuid_or_none(evidence.get("maintenance_record_id")),
                media_id=self._uuid_or_none(evidence.get("media_id")),
                evidence_text=evidence_text,
                confidence=max(0.0, min(1.0, float(confidence or 0.6))),
            )
        )

    def _refresh_run_counts(self, run_id: UUID) -> None:
        run = self.repository.get_run(run_id)
        if not run:
            return
        candidates, _ = self.repository.list_candidates(run_id=run_id, page=1, page_size=1000)
        run.candidate_count = len(candidates)
        run.approved_count = sum(1 for item in candidates if item.status == "approved")
        run.rejected_count = sum(1 for item in candidates if item.status == "rejected")
        self.repository.update_run(run)

    def _get_pending(self, candidate_id: UUID) -> KGCandidate:
        candidate = self.repository.get_candidate(candidate_id)
        if not candidate:
            raise KGCandidateServiceError("Knowledge graph candidate not found")
        if candidate.status != "pending":
            raise KGCandidateServiceError("Only pending candidates can be reviewed")
        return candidate

    @staticmethod
    def _require_reviewer(current_user: User) -> None:
        if current_user.role not in REVIEWER_ROLES:
            raise KGCandidatePermissionError("Only experts and admins can review graph candidates")

    @staticmethod
    def _uuid_or_none(value: Any) -> UUID | None:
        if not value:
            return None
        if isinstance(value, UUID):
            return value
        try:
            return UUID(str(value))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _serialize_candidate(candidate: KGCandidate) -> dict[str, Any]:
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
