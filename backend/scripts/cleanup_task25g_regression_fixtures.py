from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, func, select

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal
from app.models import KnowledgeDocument, QARecord, User, VectorIndexRun
from task25g_common import now_iso, read_json, write_json


def main() -> int:
    snapshot = read_json("snapshot.json", {})
    pre = read_json("regression_pre_database.json", {})
    created_at = snapshot.get("created_at")
    expected_documents = int(pre.get("knowledge_documents", -1))
    if not created_at or expected_documents < 0:
        raise SystemExit("Task 25G snapshot and pre-regression DB baseline are required")
    since = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))

    with SessionLocal() as db:
        documents = list(db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.created_at >= since)))
        task24d = [
            item for item in documents
            if str(item.title or "").startswith("Task24D_")
            and (str(item.title or "").endswith(" upload security") or str(item.title or "").endswith(" RBAC upload"))
            and item.source in {"task24d_security", "user_upload"}
            and item.source_type == "user_upload"
            and item.document_type == "manual"
        ]
        task24b = [
            item for item in documents
            if str(item.title or "").startswith("Task24B_DashVector_")
            and item.source_type == "script_fixture"
            and str(item.source or "").startswith("Task24B_DashVector_")
            and (item.metadata_json or {}).get("purpose") == "dashvector_hybrid_rag_flow"
            and (item.metadata_json or {}).get("is_test_fixture") is True
        ]
        selected_ids = {item.id for item in task24d + task24b}
        unexpected = [
            item for item in documents
            if (str(item.title or "").startswith("Task24D_") or str(item.title or "").startswith("Task24B_DashVector_"))
            and item.id not in selected_ids
        ]
        if unexpected:
            raise SystemExit("refusing cleanup: a regression fixture marker has an unexpected shape")
        users = list(db.scalars(select(User).where(User.created_at >= since, User.username.like("Task24B_DashVector_%"))))
        user_ids = {item.id for item in users}
        qa_count = int(db.scalar(select(func.count()).select_from(QARecord).where(QARecord.created_by.in_(user_ids))) or 0) if user_ids else 0
        run_count = int(db.scalar(select(func.count()).select_from(VectorIndexRun).where(VectorIndexRun.created_by.in_(user_ids))) or 0) if user_ids else 0
        if user_ids:
            db.execute(delete(QARecord).where(QARecord.created_by.in_(user_ids)))
            db.execute(delete(VectorIndexRun).where(VectorIndexRun.created_by.in_(user_ids)))
        if selected_ids:
            db.execute(delete(KnowledgeDocument).where(KnowledgeDocument.id.in_(selected_ids)))
        if user_ids:
            db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()

    with SessionLocal() as verify:
        document_count = int(verify.scalar(select(func.count()).select_from(KnowledgeDocument)) or 0)
        remaining_documents = int(verify.scalar(select(func.count()).select_from(KnowledgeDocument).where(KnowledgeDocument.id.in_(selected_ids))) or 0) if selected_ids else 0
        remaining_users = int(verify.scalar(select(func.count()).select_from(User).where(User.id.in_(user_ids))) or 0) if user_ids else 0
    passed = remaining_documents == 0 and remaining_users == 0 and document_count == expected_documents
    payload = {
        "generated_at": now_iso(), "status": "PASS" if passed else "FAIL",
        "scope": "Task 25G post-snapshot Task24D and Task24B regression fixtures only",
        "deleted_documents": len(selected_ids), "deleted_task24d_documents": len(task24d),
        "deleted_task24b_documents": len(task24b), "deleted_qa_records": qa_count,
        "deleted_vector_index_runs": run_count, "deleted_users": len(user_ids),
        "remaining_documents": remaining_documents, "remaining_users": remaining_users,
        "database_document_count": document_count, "expected_database_document_count": expected_documents,
        "formal_documents_deleted": 0,
    }
    write_json("regression_fixture_cleanup.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

