from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Device,
    DeviceMaintenanceRecord,
    DiagnosisRecord,
    KnowledgeChunk,
    KnowledgeDocument,
    MaintenanceTask,
    ModelOutputCorrection,
    QARecord,
    SOPExecutionRecord,
    SOPTemplate,
    UploadedMedia,
)


class SystemStatisticsRepository:
    def __init__(self, db: Session):
        self.db = db

    def collect(self) -> dict:
        return {
            "devices": {
                "total": self._count(Device),
                "normal": self._count(Device, Device.status == "normal"),
                "fault": self._count(Device, Device.status == "fault"),
                "maintenance": self._count(Device, Device.status == "maintenance"),
                "offline": self._count(Device, Device.status == "offline"),
                "retired": self._count(Device, Device.status == "retired"),
            },
            "knowledge": {
                "documents": self._count(KnowledgeDocument),
                "chunks": self._count(KnowledgeChunk),
                "pending_review": self._count(KnowledgeDocument, KnowledgeDocument.review_status.in_(["pending_review", "draft"])),
                "approved": self._count(KnowledgeDocument, KnowledgeDocument.review_status == "approved"),
                "rejected": self._count(KnowledgeDocument, KnowledgeDocument.review_status == "rejected"),
                "archived": self._count(KnowledgeDocument, KnowledgeDocument.review_status == "archived"),
            },
            "qa": {
                "records": self._count(QARecord),
            },
            "diagnosis": {
                "records": self._count(DiagnosisRecord),
            },
            "tasks": {
                "total": self._count(MaintenanceTask),
                "pending": self._count(MaintenanceTask, MaintenanceTask.status == "pending"),
                "assigned": self._count(MaintenanceTask, MaintenanceTask.status == "assigned"),
                "in_progress": self._count(MaintenanceTask, MaintenanceTask.status == "in_progress"),
                "completed": self._count(MaintenanceTask, MaintenanceTask.status == "completed"),
                "cancelled": self._count(MaintenanceTask, MaintenanceTask.status == "cancelled"),
            },
            "sop": {
                "templates": self._count(SOPTemplate),
                "executions": self._count(SOPExecutionRecord),
            },
            "maintenance": {
                "records": self._count(DeviceMaintenanceRecord),
            },
            "media": {
                "items": self._count(UploadedMedia),
            },
            "corrections": {
                "pending": self._count(ModelOutputCorrection, ModelOutputCorrection.review_status == "pending_review"),
                "accepted": self._count(ModelOutputCorrection, ModelOutputCorrection.review_status == "accepted"),
                "rejected": self._count(ModelOutputCorrection, ModelOutputCorrection.review_status == "rejected"),
            },
        }

    def _count(self, model, *filters) -> int:
        statement = select(func.count()).select_from(model)
        if filters:
            statement = statement.where(*filters)
        return self.db.scalar(statement) or 0
