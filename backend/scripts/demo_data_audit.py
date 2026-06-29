from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import SessionLocal
from app.models import (
    Device,
    KnowledgeDocument,
    MaintenanceTask,
    ModelOutputCorrection,
    QARecord,
    SOPTemplate,
    User,
)


@dataclass
class AuditSection:
    name: str
    total: int
    samples: list[dict[str, Any]]
    cleanup_recommendation: str


def count_query(session, model, *criteria) -> int:
    statement = select(func.count()).select_from(model)
    if criteria:
        statement = statement.where(*criteria)
    return int(session.execute(statement).scalar_one())


def sample_rows(session, model, columns: list[str], *criteria, limit: int = 10) -> list[dict[str, Any]]:
    statement = select(model)
    if criteria:
        statement = statement.where(*criteria)
    statement = statement.order_by(model.created_at.desc()).limit(limit)
    rows = session.execute(statement).scalars().all()
    samples: list[dict[str, Any]] = []
    for row in rows:
        item: dict[str, Any] = {}
        for column in columns:
            value = getattr(row, column, None)
            item[column] = str(value) if value is not None else None
        samples.append(item)
    return samples


def main() -> int:
    sections: list[AuditSection] = []
    try:
        with SessionLocal() as session:
            test_user_filter = or_(
                User.username.ilike("%test%"),
                User.username.ilike("%task%"),
                User.username.in_(["viewer_test", "engineer_task10", "viewer_task09", "viewer_task10"]),
            )
            sections.append(
                AuditSection(
                    name="test_users",
                    total=count_query(session, User, test_user_filter),
                    samples=sample_rows(session, User, ["id", "username", "role", "status"], test_user_filter),
                    cleanup_recommendation="Review test/demo accounts before final delivery; disable rather than delete if audit history depends on them.",
                )
            )

            disposable_doc_filter = or_(
                KnowledgeDocument.title.ilike("Task11A_Disposable%"),
                KnowledgeDocument.source.ilike("%disposable%"),
                KnowledgeDocument.source.ilike("%Task11A%"),
            )
            sections.append(
                AuditSection(
                    name="disposable_documents",
                    total=count_query(session, KnowledgeDocument, disposable_doc_filter),
                    samples=sample_rows(
                        session,
                        KnowledgeDocument,
                        ["id", "title", "source", "parse_status", "review_status", "created_at"],
                        disposable_doc_filter,
                    ),
                    cleanup_recommendation="Archive disposable documents through review workflow if they should not appear in demos.",
                )
            )

            demo_device_filter = or_(
                Device.device_code.ilike("%demo%"),
                Device.device_name.ilike("%demo%"),
                Device.description.ilike("%demo%"),
            )
            sections.append(
                AuditSection(
                    name="demo_devices",
                    total=count_query(session, Device, demo_device_filter),
                    samples=sample_rows(
                        session,
                        Device,
                        ["id", "device_code", "device_name", "manufacturer", "product_series", "status"],
                        demo_device_filter,
                    ),
                    cleanup_recommendation="Keep one Huawei and one Sungrow demo inverter for acceptance; retire extra demo devices if needed.",
                )
            )

            demo_knowledge_filter = or_(
                KnowledgeDocument.source.ilike("%demo%"),
                KnowledgeDocument.title.ilike("%demo%"),
                KnowledgeDocument.summary.ilike("%demo%"),
            )
            sections.append(
                AuditSection(
                    name="demo_knowledge",
                    total=count_query(session, KnowledgeDocument, demo_knowledge_filter),
                    samples=sample_rows(
                        session,
                        KnowledgeDocument,
                        ["id", "title", "manufacturer", "product_series", "document_type", "source", "review_status"],
                        demo_knowledge_filter,
                    ),
                    cleanup_recommendation="Retain curated Huawei/Sungrow demo documents; archive disposable verification documents.",
                )
            )

            demo_sop_filter = or_(
                SOPTemplate.title.ilike("%demo%"),
                SOPTemplate.title.ilike("%Task%"),
                SOPTemplate.compliance_notes.ilike("%demo%"),
            )
            sections.append(
                AuditSection(
                    name="demo_sop",
                    total=count_query(session, SOPTemplate, demo_sop_filter),
                    samples=sample_rows(
                        session,
                        SOPTemplate,
                        ["id", "title", "manufacturer", "product_series", "fault_type", "status"],
                        demo_sop_filter,
                    ),
                    cleanup_recommendation="Keep active demo SOP templates only; archive temporary verification templates.",
                )
            )

            demo_task_filter = or_(
                MaintenanceTask.title.ilike("%demo%"),
                MaintenanceTask.title.ilike("%Task%"),
                MaintenanceTask.fault_description.ilike("%demo%"),
            )
            sections.append(
                AuditSection(
                    name="demo_tasks",
                    total=count_query(session, MaintenanceTask, demo_task_filter),
                    samples=sample_rows(
                        session,
                        MaintenanceTask,
                        ["id", "title", "manufacturer", "product_series", "task_status", "priority"],
                        demo_task_filter,
                    ),
                    cleanup_recommendation="Keep representative tasks for demos; avoid deleting historical linked records.",
                )
            )

            correction_filter = or_(
                ModelOutputCorrection.correction_reason.ilike("%disposable%"),
                ModelOutputCorrection.correction_reason.ilike("%demo%"),
                ModelOutputCorrection.correction_reason.ilike("%Task%"),
                ModelOutputCorrection.source_trace_id.ilike("%Task%"),
            )
            sections.append(
                AuditSection(
                    name="corrections",
                    total=count_query(session, ModelOutputCorrection, correction_filter),
                    samples=sample_rows(
                        session,
                        ModelOutputCorrection,
                        ["id", "source_type", "source_trace_id", "review_status", "correction_reason"],
                        correction_filter,
                    ),
                    cleanup_recommendation="Resolve or leave as review-history evidence; do not delete automatically.",
                )
            )

            suspicious_qa_filter = or_(
                QARecord.question.ilike("??%"),
                QARecord.question.ilike("%???%"),
                QARecord.question.ilike("%�%"),
                QARecord.normalized_query.ilike("??%"),
                QARecord.normalized_query.ilike("%???%"),
                QARecord.normalized_query.ilike("%�%"),
            )
            sections.append(
                AuditSection(
                    name="suspicious_qa_records",
                    total=count_query(session, QARecord, suspicious_qa_filter),
                    samples=sample_rows(
                        session,
                        QARecord,
                        ["id", "trace_id", "question", "model_provider", "created_at"],
                        suspicious_qa_filter,
                    ),
                    cleanup_recommendation="Review encoding issue source; keep records until traceability policy allows archival.",
                )
            )
    except SQLAlchemyError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    report = {
        "status": "passed",
        "mode": "read_only_audit",
        "sections": [asdict(section) for section in sections],
        "sql_cleanup_note": "No DELETE statements were executed. Generate manual archive/update SQL only after human review.",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
