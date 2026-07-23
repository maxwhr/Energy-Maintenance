from datetime import datetime, timezone
from time import perf_counter

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import BusinessException
from app.core.retrieval_lab_config import get_retrieval_lab_settings
from app.core.security_config import collect_security_status
from app.models import (
    DiagnosisRecord,
    MaintenanceTask,
    QARecord,
    SOPTemplate,
    UploadedMedia,
    User,
)
from app.schemas.common import success_response
from app.services.deployment_readiness_service import DeploymentReadinessService
from app.services.maintenance_workflow_status_service import (
    MaintenanceWorkflowStatusService,
)
from app.services.multimodal_quality_status_service import (
    MultimodalQualityStatusService,
)
from app.services.rag_performance_trace_service import RagPerformanceTraceService
from app.services.retrieval_status_service import RetrievalStatusService
from app.services.system_statistics_service import SystemStatisticsService


router = APIRouter(tags=["system"])


@router.get("/system/deployment-readiness")
def get_deployment_readiness(
    current_user: User = Depends(get_current_user),
) -> dict:
    return success_response(DeploymentReadinessService.collect(role=current_user.role))


@router.get("/system/maintenance-workflow/status")
def get_maintenance_workflow_status(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> dict:
    return success_response(MaintenanceWorkflowStatusService(db).get_status())


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
    settings = get_settings()
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
        "security": collect_security_status(settings),
        "retrieval": {
            "default_strategy": settings.RETRIEVAL_DEFAULT_MODE,
            "manufacturers": ["huawei", "sungrow"],
            "approved_active_document_count": 0,
            "approved_active_chunk_count": 0,
            "citation_validity_rate": 0.0,
            "citation_count": 0,
            "valid_citation_count": 0,
            "controlled_refusal_enabled": True,
            "vector_enabled": bool(
                settings.VECTOR_SEARCH_ENABLED and settings.DASHVECTOR_ENABLED
            ),
            "embedding_enabled": bool(settings.EMBEDDING_ENABLED),
            "rerank_enabled": bool(
                settings.RERANK_ENABLED
                or settings.RETRIEVAL_FEATURE_RERANK_ENABLED
                or settings.RAG_DEDICATED_RERANK_ENABLED
            ),
            "external_provider_configured": False,
            "external_real_calls_enabled": bool(
                settings.EXTERNAL_REAL_CALLS_ENABLED
            ),
            "latest_formal_index": {
                "status": "database_offline",
                "backend": None,
                "finished_at": None,
            },
            "lab_enabled": bool(
                get_retrieval_lab_settings().ENABLE_RETRIEVAL_LAB
            ),
        },
    }

    try:
        db.execute(text("SELECT 1"))
        payload.update(
            {
                "database_status": "online",
                "database_latency_ms": round(
                    (perf_counter() - started_at) * 1000, 2
                ),
                "document_count": db.scalar(
                    text(
                        "SELECT count(*) FROM knowledge_documents "
                        "WHERE status != 'deleted'"
                    )
                )
                or 0,
                "chunk_count": db.scalar(
                    text(
                        "SELECT count(*) FROM knowledge_chunks "
                        "WHERE status != 'deleted'"
                    )
                )
                or 0,
                "qa_record_count": db.scalar(select(func.count(QARecord.id))) or 0,
                "diagnosis_record_count": db.scalar(
                    select(func.count(DiagnosisRecord.id))
                )
                or 0,
                "maintenance_task_count": db.scalar(
                    select(func.count(MaintenanceTask.id))
                )
                or 0,
                "media_count": db.scalar(select(func.count(UploadedMedia.id))) or 0,
                "sop_template_count": db.scalar(
                    select(func.count(SOPTemplate.id))
                )
                or 0,
                "retrieval": RetrievalStatusService(db).collect(),
            }
        )
    except Exception as exc:  # noqa: BLE001 - report reachability safely.
        payload["database_latency_ms"] = round(
            (perf_counter() - started_at) * 1000, 2
        )
        payload["database_error"] = exc.__class__.__name__

    return success_response(payload)


@router.get("/system/statistics")
def get_system_statistics(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(SystemStatisticsService(db).collect())


@router.get("/system/multimodal-quality/status")
def get_multimodal_quality_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(MultimodalQualityStatusService(db).collect())


@router.get("/system/retrieval-performance/summary")
def get_retrieval_performance_summary(
    current_user: User = Depends(get_current_user),
) -> dict:
    if current_user.role != "admin":
        raise BusinessException(
            "Admin role required",
            40303,
            http_status=403,
        )
    rows = RagPerformanceTraceService.recent()[-50:]
    totals = sorted(float(row.get("total_ms") or 0.0) for row in rows)
    p50 = totals[(len(totals) - 1) // 2] if totals else 0.0
    p95 = totals[max(0, int(len(totals) * 0.95) - 1)] if totals else 0.0
    return success_response(
        {
            "trace_count": len(rows),
            "total_p50_ms": round(p50, 3),
            "total_p95_ms": round(p95, 3),
            "query_text_exposed": False,
            "candidate_content_exposed": False,
            "latest": [
                {
                    "trace_id": row.get("trace_id"),
                    "query_hash": row.get("query_hash"),
                    "scope_fingerprint": row.get("scope_fingerprint"),
                    "mode": row.get("mode"),
                    "cache_status": row.get("cache_status"),
                    "total_ms": row.get("total_ms"),
                    "stages": row.get("stages") or {},
                }
                for row in rows[-10:]
            ],
        }
    )
