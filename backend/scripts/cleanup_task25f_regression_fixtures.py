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
from app.models import KnowledgeContribution, KnowledgeDocument, KnowledgeReviewRecord
from task25f_common import now_iso, read_json, write_json


def main() -> int:
    baseline = read_json("baseline.json", {})
    since_value = baseline.get("generated_at")
    if not since_value:
        raise SystemExit("Task 25F frozen baseline is required")
    since = datetime.fromisoformat(str(since_value).replace("Z", "+00:00"))

    with SessionLocal() as db:
        documents = list(
            db.scalars(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.created_at >= since,
                    KnowledgeDocument.title.like("Task24D\\_%", escape="\\"),
                    KnowledgeDocument.source_type == "user_upload",
                    KnowledgeDocument.document_type == "manual",
                )
            )
        )
        unexpected = [
            document
            for document in documents
            if not (
                str(document.title or "").endswith(" upload security")
                or str(document.title or "").endswith(" RBAC upload")
            )
            or document.source not in {"task24d_security", "user_upload"}
        ]
        if unexpected:
            raise SystemExit("refusing cleanup: unexpected Task24D document shape")

        document_ids = {document.id for document in documents}
        blocking = {"knowledge_contributions": 0, "knowledge_review_records": 0}
        if document_ids:
            blocking["knowledge_contributions"] = int(
                db.scalar(
                    select(func.count())
                    .select_from(KnowledgeContribution)
                    .where(KnowledgeContribution.approved_document_id.in_(document_ids))
                )
                or 0
            )
            blocking["knowledge_review_records"] = int(
                db.scalar(
                    select(func.count())
                    .select_from(KnowledgeReviewRecord)
                    .where(KnowledgeReviewRecord.document_id.in_(document_ids))
                )
                or 0
            )
        if any(blocking.values()):
            raise SystemExit(f"refusing cleanup: fixtures gained business references {blocking}")

        if document_ids:
            db.execute(delete(KnowledgeDocument).where(KnowledgeDocument.id.in_(document_ids)))
        db.commit()

    expected_counts = baseline.get("database_counts") or {}
    with SessionLocal() as verify:
        document_count = int(
            verify.scalar(select(func.count()).select_from(KnowledgeDocument)) or 0
        )
        remaining = int(
            verify.scalar(
                select(func.count())
                .select_from(KnowledgeDocument)
                .where(KnowledgeDocument.id.in_(document_ids))
            )
            or 0
        ) if document_ids else 0

    passed = remaining == 0 and document_count == int(expected_counts.get("knowledge_documents", -1))
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if passed else "FAIL",
        "scope": "Task 25F run-created Task24D security/RBAC upload fixtures only",
        "deleted_documents": len(document_ids),
        "document_ids": sorted(str(value) for value in document_ids),
        "blocking_business_references": blocking,
        "remaining_documents": remaining,
        "database_document_count": document_count,
        "expected_database_document_count": expected_counts.get("knowledge_documents"),
        "formal_documents_deleted": 0,
    }
    write_json("regression_fixture_cleanup.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
