from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AgentApproval,
    AgentArtifact,
    AgentRun,
    Device,
    MediaAIAnalysis,
    MediaOCRResult,
    MultimodalDiagnosticHypothesis,
    MultimodalEvidenceConflict,
    MultimodalEvidenceItem,
    MultimodalMaintenanceCase,
    OperationLog,
    UploadedMedia,
)


class MultimodalCaseRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_case(self, item: MultimodalMaintenanceCase) -> MultimodalMaintenanceCase:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def save_case(self, item: MultimodalMaintenanceCase) -> MultimodalMaintenanceCase:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def get_case(self, case_id: str) -> MultimodalMaintenanceCase | None:
        return self.db.scalar(select(MultimodalMaintenanceCase).where(MultimodalMaintenanceCase.case_id == case_id))

    def get_device(self, device_id: UUID) -> Device | None:
        return self.db.get(Device, device_id)

    def get_media(self, media_id: UUID) -> UploadedMedia | None:
        return self.db.get(UploadedMedia, media_id)

    def get_media_items(self, media_ids: list[UUID]) -> list[UploadedMedia]:
        if not media_ids:
            return []
        rows = list(self.db.scalars(select(UploadedMedia).where(UploadedMedia.id.in_(media_ids))))
        mapping = {item.id: item for item in rows}
        return [mapping[item_id] for item_id in media_ids if item_id in mapping]

    def latest_ocr_result(self, media_id: UUID) -> MediaOCRResult | None:
        return self.db.scalar(select(MediaOCRResult).where(
            MediaOCRResult.media_id == media_id,
            MediaOCRResult.status == "succeeded",
        ).order_by(MediaOCRResult.created_at.desc()).limit(1))

    def latest_ai_analysis(self, media_id: UUID) -> MediaAIAnalysis | None:
        return self.db.scalar(select(MediaAIAnalysis).where(
            MediaAIAnalysis.media_id == media_id,
        ).order_by(MediaAIAnalysis.created_at.desc()).limit(1))

    def get_by_idempotency_key(self, key: str) -> MultimodalMaintenanceCase | None:
        return self.db.scalar(
            select(MultimodalMaintenanceCase).where(MultimodalMaintenanceCase.idempotency_key == key)
        )

    def list_cases(
        self,
        *,
        created_by: UUID | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[MultimodalMaintenanceCase], int]:
        filters = []
        if created_by:
            filters.append(MultimodalMaintenanceCase.created_by == created_by)
        if status:
            filters.append(MultimodalMaintenanceCase.status == status)
        count = select(func.count()).select_from(MultimodalMaintenanceCase)
        query = select(MultimodalMaintenanceCase)
        if filters:
            count = count.where(*filters)
            query = query.where(*filters)
        query = query.order_by(MultimodalMaintenanceCase.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return list(self.db.scalars(query)), int(self.db.scalar(count) or 0)

    def create_evidence(self, item: MultimodalEvidenceItem) -> MultimodalEvidenceItem:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def save_evidence(self, item: MultimodalEvidenceItem) -> MultimodalEvidenceItem:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def get_evidence(self, case_id: str, evidence_id: str) -> MultimodalEvidenceItem | None:
        return self.db.scalar(select(MultimodalEvidenceItem).where(
            MultimodalEvidenceItem.case_id == case_id,
            MultimodalEvidenceItem.evidence_id == evidence_id,
        ))

    def get_evidence_by_identity(self, case_id: str, source_hash: str, evidence_type: str) -> MultimodalEvidenceItem | None:
        return self.db.scalar(select(MultimodalEvidenceItem).where(
            MultimodalEvidenceItem.case_id == case_id,
            MultimodalEvidenceItem.source_hash == source_hash,
            MultimodalEvidenceItem.evidence_type == evidence_type,
        ))

    def list_evidence(self, case_id: str) -> list[MultimodalEvidenceItem]:
        return list(self.db.scalars(select(MultimodalEvidenceItem).where(
            MultimodalEvidenceItem.case_id == case_id
        ).order_by(MultimodalEvidenceItem.created_at, MultimodalEvidenceItem.evidence_id)))

    def create_conflict(self, item: MultimodalEvidenceConflict) -> MultimodalEvidenceConflict:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def get_conflict(self, conflict_id: str) -> MultimodalEvidenceConflict | None:
        return self.db.scalar(select(MultimodalEvidenceConflict).where(
            MultimodalEvidenceConflict.conflict_id == conflict_id
        ))

    def list_conflicts(self, case_id: str) -> list[MultimodalEvidenceConflict]:
        return list(self.db.scalars(select(MultimodalEvidenceConflict).where(
            MultimodalEvidenceConflict.case_id == case_id
        ).order_by(MultimodalEvidenceConflict.created_at)))

    def create_hypothesis(self, item: MultimodalDiagnosticHypothesis) -> MultimodalDiagnosticHypothesis:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def get_hypothesis(self, hypothesis_id: str) -> MultimodalDiagnosticHypothesis | None:
        return self.db.scalar(select(MultimodalDiagnosticHypothesis).where(
            MultimodalDiagnosticHypothesis.hypothesis_id == hypothesis_id
        ))

    def save_hypothesis(self, item: MultimodalDiagnosticHypothesis) -> MultimodalDiagnosticHypothesis:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def get_agent_run(self, run_id: str) -> AgentRun | None:
        return self.db.scalar(select(AgentRun).where(AgentRun.run_id == run_id))

    def create_agent_run(self, item: AgentRun) -> AgentRun:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def save_agent_run(self, item: AgentRun) -> AgentRun:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def create_artifact(self, item: AgentArtifact) -> AgentArtifact:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def get_artifact(self, artifact_id: UUID) -> AgentArtifact | None:
        return self.db.get(AgentArtifact, artifact_id)

    def get_artifact_by_source(self, source_id: str, artifact_type: str) -> AgentArtifact | None:
        return self.db.scalar(select(AgentArtifact).where(
            AgentArtifact.source_type == "multimodal_case",
            AgentArtifact.source_id == source_id,
            AgentArtifact.artifact_type == artifact_type,
        ).order_by(AgentArtifact.created_at.desc()).limit(1))

    def create_approval(self, item: AgentApproval) -> AgentApproval:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def get_approved_sop_approval(self, run_id: str) -> AgentApproval | None:
        return self.db.scalar(select(AgentApproval).where(
            AgentApproval.run_id == run_id,
            AgentApproval.approval_type == "sop_approval",
            AgentApproval.status == "approved",
        ).order_by(AgentApproval.created_at.desc()).limit(1))

    def list_hypotheses(self, case_id: str) -> list[MultimodalDiagnosticHypothesis]:
        return list(self.db.scalars(select(MultimodalDiagnosticHypothesis).where(
            MultimodalDiagnosticHypothesis.case_id == case_id
        ).order_by(MultimodalDiagnosticHypothesis.confidence.desc())))

    def add_audit(self, item: OperationLog) -> OperationLog:
        self.db.add(item)
        self.db.flush()
        return item

    def list_audit(self, case_id: str) -> list[OperationLog]:
        return list(self.db.scalars(select(OperationLog).where(
            OperationLog.module == "multimodal_case",
            OperationLog.target_type == "multimodal_case",
            OperationLog.target_id == case_id,
        ).order_by(OperationLog.created_at)))

    def counts(self, case_id: str) -> dict[str, int]:
        evidence = int(self.db.scalar(select(func.count()).select_from(MultimodalEvidenceItem).where(
            MultimodalEvidenceItem.case_id == case_id
        )) or 0)
        regions = int(self.db.scalar(select(func.count()).select_from(MultimodalEvidenceItem).where(
            MultimodalEvidenceItem.case_id == case_id,
            MultimodalEvidenceItem.region_id.is_not(None),
        )) or 0)
        conflicts = int(self.db.scalar(select(func.count()).select_from(MultimodalEvidenceConflict).where(
            MultimodalEvidenceConflict.case_id == case_id
        )) or 0)
        hypotheses = int(self.db.scalar(select(func.count()).select_from(MultimodalDiagnosticHypothesis).where(
            MultimodalDiagnosticHypothesis.case_id == case_id
        )) or 0)
        return {"evidence_count": evidence, "region_count": regions, "conflict_count": conflicts, "hypothesis_count": hypotheses}
