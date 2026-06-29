"""Pydantic schemas package."""

from app.schemas.auth import AuthUserRead, LoginRequest, LoginResponse, UserCreateRequest, UserManagementRead, UserUpdateRequest
from app.schemas.common import ApiResponse
from app.schemas.device_history import (
    DeviceMaintenanceRecordCreate,
    DeviceMaintenanceRecordRead,
    DeviceMaintenanceRecordUpdate,
)
from app.schemas.knowledge import KnowledgeChunkRead, KnowledgeDocumentCreate, KnowledgeDocumentRead
from app.schemas.maintenance import MaintenanceTaskCreate, MaintenanceTaskRead, MaintenanceTaskStatusUpdate
from app.schemas.media import UploadedMediaCreate, UploadedMediaRead, UploadedMediaUpdate
from app.schemas.record import DiagnosisRecordRead, ModelCallLogCreate, ModelCallLogRead, ModelCallLogUpdate, QARecordRead
from app.schemas.review import (
    KnowledgeContributionCreate,
    KnowledgeContributionRead,
    KnowledgeContributionUpdate,
    KnowledgeReviewRecordCreate,
    KnowledgeReviewRecordRead,
    ModelOutputCorrectionCreate,
    ModelOutputCorrectionRead,
    ModelOutputCorrectionUpdate,
)
from app.schemas.sop import (
    SOPExecutionRecordCreate,
    SOPExecutionRecordRead,
    SOPExecutionRecordUpdate,
    SOPTemplateCreate,
    SOPTemplateRead,
    SOPTemplateUpdate,
)
from app.schemas.system import DeviceCreate, DeviceRead, DeviceUpdate, SystemInfo, SystemStatus, UserCreate, UserRead, UserUpdate

__all__ = [
    "ApiResponse",
    "LoginRequest",
    "LoginResponse",
    "AuthUserRead",
    "UserCreateRequest",
    "UserUpdateRequest",
    "UserManagementRead",
    "UserCreate",
    "UserUpdate",
    "UserRead",
    "DeviceCreate",
    "DeviceUpdate",
    "DeviceRead",
    "KnowledgeDocumentCreate",
    "KnowledgeDocumentRead",
    "KnowledgeChunkRead",
    "QARecordRead",
    "DiagnosisRecordRead",
    "MaintenanceTaskCreate",
    "MaintenanceTaskRead",
    "MaintenanceTaskStatusUpdate",
    "UploadedMediaCreate",
    "UploadedMediaUpdate",
    "UploadedMediaRead",
    "DeviceMaintenanceRecordCreate",
    "DeviceMaintenanceRecordUpdate",
    "DeviceMaintenanceRecordRead",
    "KnowledgeContributionCreate",
    "KnowledgeContributionUpdate",
    "KnowledgeContributionRead",
    "KnowledgeReviewRecordCreate",
    "KnowledgeReviewRecordRead",
    "ModelOutputCorrectionCreate",
    "ModelOutputCorrectionUpdate",
    "ModelOutputCorrectionRead",
    "ModelCallLogCreate",
    "ModelCallLogUpdate",
    "ModelCallLogRead",
    "SOPTemplateCreate",
    "SOPTemplateUpdate",
    "SOPTemplateRead",
    "SOPExecutionRecordCreate",
    "SOPExecutionRecordUpdate",
    "SOPExecutionRecordRead",
    "SystemInfo",
    "SystemStatus",
]
