"""Database repositories."""

from app.repositories.device_history_repository import DeviceHistoryRepository
from app.repositories.device_repository import DeviceRepository
from app.repositories.correction_repository import CorrectionRepository
from app.repositories.diagnosis_repository import DiagnosisRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.maintenance_record_repository import MaintenanceRecordRepository
from app.repositories.maintenance_task_repository import MaintenanceTaskRepository
from app.repositories.media_repository import MediaRepository
from app.repositories.model_call_log_repository import ModelCallLogRepository
from app.repositories.qa_record_repository import QARecordRepository
from app.repositories.record_center_repository import RecordCenterRepository
from app.repositories.retrieval_repository import RetrievalRepository
from app.repositories.review_repository import ReviewRepository
from app.repositories.sop_repository import SOPRepository
from app.repositories.system_statistics_repository import SystemStatisticsRepository
from app.repositories.user_repository import UserRepository

__all__ = [
    "DeviceHistoryRepository",
    "DeviceRepository",
    "CorrectionRepository",
    "DiagnosisRepository",
    "KnowledgeRepository",
    "MaintenanceRecordRepository",
    "MaintenanceTaskRepository",
    "MediaRepository",
    "ModelCallLogRepository",
    "QARecordRepository",
    "RecordCenterRepository",
    "RetrievalRepository",
    "ReviewRepository",
    "SOPRepository",
    "SystemStatisticsRepository",
    "UserRepository",
]
