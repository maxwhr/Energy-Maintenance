from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    MultimodalDiagnosticHypothesis,
    MultimodalEvidenceConflict,
    MultimodalEvidenceItem,
    MultimodalMaintenanceCase,
    OperationLog,
)


class MultimodalQualityStatusService:
    """Report production multimodal state without lab artifact files."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def collect(self) -> dict:
        cases = self._count(MultimodalMaintenanceCase)
        evidence_items = self._count(MultimodalEvidenceItem)
        return {
            "feature": "multimodal_maintenance",
            "status": "active" if cases or evidence_items else "ready",
            "case_model": {
                "cases": cases,
                "evidence_items": evidence_items,
                "regions": int(
                    self.db.scalar(
                        select(func.count())
                        .select_from(MultimodalEvidenceItem)
                        .where(MultimodalEvidenceItem.region_id.is_not(None))
                    )
                    or 0
                ),
                "conflicts": self._count(MultimodalEvidenceConflict),
                "hypotheses": self._count(MultimodalDiagnosticHypothesis),
                "audits": int(
                    self.db.scalar(
                        select(func.count())
                        .select_from(OperationLog)
                        .where(OperationLog.module == "multimodal_case")
                    )
                    or 0
                ),
            },
            "providers": {
                "external_real_calls_enabled": bool(
                    self.settings.EXTERNAL_REAL_CALLS_ENABLED
                ),
                "ocr_enabled": bool(
                    self.settings.OCR_API_ENABLED or self.settings.OCR_ENABLED
                ),
                "vision_enabled": bool(
                    self.settings.MIMO_ENABLED
                    or self.settings.CLOUD_VISION_ENABLED
                ),
                "credentials_exposed": False,
                "provider_payload_exposed": False,
            },
            "retrieval": {
                "default_strategy": self.settings.RETRIEVAL_DEFAULT_MODE,
                "manufacturers": ["huawei", "sungrow"],
                "controlled_refusal_enabled": True,
            },
            "boundaries": {
                "automatic_sop_approval": False,
                "automatic_formal_task_creation": False,
                "knowledge_approval_modified": False,
                "expert_verified_written": False,
                "vector_index_modified": False,
            },
        }

    def _count(self, model) -> int:
        return int(
            self.db.scalar(select(func.count()).select_from(model)) or 0
        )
