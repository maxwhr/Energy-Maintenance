from __future__ import annotations

from pydantic import BaseModel


class DeviceStatistics(BaseModel):
    total: int = 0
    normal: int = 0
    fault: int = 0
    maintenance: int = 0
    offline: int = 0
    retired: int = 0


class KnowledgeStatistics(BaseModel):
    documents: int = 0
    chunks: int = 0
    pending_review: int = 0
    approved: int = 0
    rejected: int = 0
    archived: int = 0


class QAStatistics(BaseModel):
    records: int = 0


class DiagnosisStatistics(BaseModel):
    records: int = 0


class TaskStatistics(BaseModel):
    total: int = 0
    pending: int = 0
    assigned: int = 0
    in_progress: int = 0
    completed: int = 0
    cancelled: int = 0


class SOPStatistics(BaseModel):
    templates: int = 0
    executions: int = 0


class MaintenanceStatistics(BaseModel):
    records: int = 0


class MediaStatistics(BaseModel):
    items: int = 0


class CorrectionStatistics(BaseModel):
    pending: int = 0
    accepted: int = 0
    rejected: int = 0


class SystemStatistics(BaseModel):
    devices: DeviceStatistics
    knowledge: KnowledgeStatistics
    qa: QAStatistics
    diagnosis: DiagnosisStatistics
    tasks: TaskStatistics
    sop: SOPStatistics
    maintenance: MaintenanceStatistics
    media: MediaStatistics
    corrections: CorrectionStatistics
