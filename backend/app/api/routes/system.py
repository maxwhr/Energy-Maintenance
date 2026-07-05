from datetime import datetime, timezone
from time import perf_counter

from fastapi import APIRouter, Depends
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.config import get_settings
from app.core.security_config import collect_security_status
from app.models import (
    DiagnosisRecord,
    KnowledgeChunk,
    KnowledgeDocument,
    MaintenanceTask,
    QARecord,
    SOPTemplate,
    UploadedMedia,
    User,
)
from app.schemas.common import success_response
from app.services.system_statistics_service import SystemStatisticsService

router = APIRouter(tags=["system"])


@router.get("/system/info")
def get_system_info() -> dict:
    return success_response(
        {
            "project": "Energy-Maintenance",
            "scope": "Huawei and Sungrow PV inverter maintenance knowledge retrieval and work-assistance system",
            "manufacturers": ["huawei", "sungrow"],
            "device_type": "pv_inverter",
            "product_series": ["SUN2000", "FusionSolar", "SG"],
            "deployment_target": "LoongArch + Kylin native deployment",
            "formal_database": "PostgreSQL",
        }
    )


@router.get("/system/status")
def get_system_status(db: Session = Depends(get_db)) -> dict:
    checked_at = datetime.now(timezone.utc).isoformat()
    started_at = perf_counter()
    payload = {
        "service_status": "running",
        "database_status": "offline",
        "database_checked_at": checked_at,
        "database_latency_ms": None,
        "database_error": None,
        "document_count": 0,
        "chunk_count": 0,
        "qa_record_count": 0,
        "diagnosis_record_count": 0,
        "maintenance_task_count": 0,
        "media_count": 0,
        "sop_template_count": 0,
        "security": collect_security_status(get_settings()),
    }

    try:
        db.execute(text("SELECT 1"))
        payload.update(
            {
                "database_status": "online",
                "database_latency_ms": round((perf_counter() - started_at) * 1000, 2),
                "document_count": db.scalar(
                    text("SELECT count(*) FROM knowledge_documents WHERE status != 'deleted'")
                )
                or 0,
                "chunk_count": db.scalar(text("SELECT count(*) FROM knowledge_chunks WHERE status != 'deleted'")) or 0,
                "qa_record_count": db.scalar(func.count(QARecord.id)) or 0,
                "diagnosis_record_count": db.scalar(func.count(DiagnosisRecord.id)) or 0,
                "maintenance_task_count": db.scalar(func.count(MaintenanceTask.id)) or 0,
                "media_count": db.scalar(func.count(UploadedMedia.id)) or 0,
                "sop_template_count": db.scalar(func.count(SOPTemplate.id)) or 0,
            }
        )
    except Exception as exc:  # noqa: BLE001 - status endpoint must report DB reachability safely.
        payload["database_latency_ms"] = round((perf_counter() - started_at) * 1000, 2)
        payload["database_error"] = exc.__class__.__name__

    return success_response(payload)


@router.get("/system/statistics")
def get_system_statistics(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(SystemStatisticsService(db).collect())
