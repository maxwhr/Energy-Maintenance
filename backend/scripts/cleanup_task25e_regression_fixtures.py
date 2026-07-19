from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, func, select

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal
from app.models import KnowledgeContribution, KnowledgeDocument, KnowledgeReviewRecord, QARecord, User
from task25e_common import now_iso, read_json, write_json


PURPOSE = "dashvector_hybrid_rag_flow"


def main() -> int:
    baseline = read_json("integrity_baseline.json", {})
    since_value = baseline.get("generated_at")
    if not since_value:
        raise SystemExit("Task 25E integrity baseline is required for exact fixture cleanup")
    since = datetime.fromisoformat(str(since_value).replace("Z", "+00:00"))
    with SessionLocal() as db:
        documents = list(db.scalars(select(KnowledgeDocument).where(
            KnowledgeDocument.created_at >= since,
            KnowledgeDocument.source_type == "script_fixture",
            KnowledgeDocument.metadata_json["is_test_fixture"].astext == "true",
            KnowledgeDocument.metadata_json["purpose"].astext == PURPOSE,
        )))
        document_ids = {document.id for document in documents}
        markers = {str((document.metadata_json or {}).get("marker") or "") for document in documents}
        if any(not marker.startswith("Task24B_DashVector_") for marker in markers):
            raise SystemExit("refusing cleanup: unexpected fixture marker")

        blocking = {"knowledge_contributions": 0, "knowledge_review_records": 0}
        if document_ids:
            blocking["knowledge_contributions"] = int(db.scalar(select(func.count()).select_from(KnowledgeContribution).where(KnowledgeContribution.approved_document_id.in_(document_ids))) or 0)
            blocking["knowledge_review_records"] = int(db.scalar(select(func.count()).select_from(KnowledgeReviewRecord).where(KnowledgeReviewRecord.document_id.in_(document_ids))) or 0)
        if any(blocking.values()):
            raise SystemExit(f"refusing cleanup: fixture documents gained business references {blocking}")

        user_ids = set()
        for marker in markers:
            user_ids.update(db.scalars(select(User.id).where(User.username.like(f"{marker}_%"), User.created_at >= since)))
        qa_ids = set(db.scalars(select(QARecord.id).where(QARecord.created_at >= since, QARecord.created_by.in_(user_ids)))) if user_ids else set()
        if qa_ids:
            db.execute(delete(QARecord).where(QARecord.id.in_(qa_ids)))
        if document_ids:
            db.execute(delete(KnowledgeDocument).where(KnowledgeDocument.id.in_(document_ids)))
        db.commit()

    with SessionLocal() as verify:
        remaining_documents = int(verify.scalar(select(func.count()).select_from(KnowledgeDocument).where(
            KnowledgeDocument.created_at >= since,
            KnowledgeDocument.source_type == "script_fixture",
            KnowledgeDocument.metadata_json["is_test_fixture"].astext == "true",
            KnowledgeDocument.metadata_json["purpose"].astext == PURPOSE,
        )) or 0)
        remaining_qa = int(verify.scalar(select(func.count()).select_from(QARecord).where(QARecord.id.in_(qa_ids))) or 0) if qa_ids else 0
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if remaining_documents == 0 and remaining_qa == 0 else "FAIL",
        "scope": "exact Task 25E run-created script fixtures only",
        "markers": sorted(markers),
        "document_ids": sorted(str(value) for value in document_ids),
        "qa_record_ids": sorted(str(value) for value in qa_ids),
        "deleted_documents": len(document_ids),
        "deleted_qa_records": len(qa_ids),
        "blocking_business_references": blocking,
        "remaining_documents": remaining_documents,
        "remaining_qa_records": remaining_qa,
        "existing_business_rows_deleted": 0,
    }
    write_json("regression_fixture_cleanup.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
