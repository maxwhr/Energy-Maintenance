from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID

from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    KnowledgeChunkVectorIndex,
    KnowledgeDocument,
    KnowledgeReviewRecord,
    OperationLog,
)


EXPECTED_APPROVED_IDS = {
    UUID("12703ebb-4860-4a8a-bed3-11734dbcdfa5"),
    UUID("2cc85307-e1f3-4382-896f-2cdae645af11"),
    UUID("2f6e8766-df74-4e31-abd4-c4b806a538bb"),
}
OUTPUT_PATH = ROOT_DIR / ".runtime" / "task25b_r2_u3_r2" / "unexpected_approval_withdrawal.json"
BASE_URL = os.getenv("TASK25B_R2_U3_R2_BASE_URL", "http://127.0.0.1:8012")
REASON = (
    "Task 25B-R2-U3-R2 quality audit detected an unexpected approval. "
    "This long document requires individual quality review or rechunk validation before any Pilot action; "
    "SmartLogger documents are explicitly excluded from Pilot indexing."
)


def request_json(method: str, path: str, payload: dict | None = None, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        f"{BASE_URL}{path}",
        method=method,
        headers=headers,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
    )
    try:
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"API request failed for {path}: {exc}") from exc
    if result.get("code") not in {0, 200}:
        raise RuntimeError(f"API rejected {path}: {result.get('message')}")
    return result


def is_vendor_official(document: KnowledgeDocument) -> bool:
    metadata = document.metadata_json or {}
    return document.source_type in {"vendor_official", "vendor_official_html"} or metadata.get("source_provenance") == "VENDOR_OFFICIAL"


def main() -> int:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    username = os.getenv("TASK25B_R2_U3_R2_ADMIN_USERNAME", "admin")
    password = os.getenv("TASK25B_R2_U3_R2_ADMIN_PASSWORD", "admin123456")
    login = request_json("POST", "/api/auth/login", {"username": username, "password": password})["data"]
    token = login["access_token"]
    actor = login["user"]
    if actor.get("role") not in {"admin", "expert"}:
        raise RuntimeError("Withdrawal actor is not an admin/expert")

    with SessionLocal() as session:
        approved_documents = list(
            session.scalars(select(KnowledgeDocument).where(KnowledgeDocument.review_status == "approved"))
        )
        official_approved = [item for item in approved_documents if is_vendor_official(item)]
        unexpected = [item for item in official_approved if item.id not in EXPECTED_APPROVED_IDS]
        before = []
        for document in unexpected:
            pilot_vectors = session.scalar(
                select(KnowledgeChunkVectorIndex)
                .where(
                    KnowledgeChunkVectorIndex.document_id == document.id,
                    KnowledgeChunkVectorIndex.namespace == "pilot_r2",
                    KnowledgeChunkVectorIndex.index_status == "active",
                )
                .limit(1)
            )
            if pilot_vectors is not None:
                raise RuntimeError(f"Refusing withdrawal for {document.id}: active pilot_r2 vector exists")
            before.append(
                {
                    "document_id": str(document.id),
                    "title": document.title,
                    "document_type": document.document_type,
                    "chunk_count": document.chunk_count,
                    "review_status": document.review_status,
                    "approved_for_pilot": bool((document.metadata_json or {}).get("approved_for_pilot")),
                    "reviewed_by": str(document.reviewed_by) if document.reviewed_by else None,
                    "reviewed_at": document.reviewed_at.isoformat() if document.reviewed_at else None,
                    "pilot_r2_active_vectors": 0,
                }
            )

        api_results = []
        for document in unexpected:
            result = request_json(
                "POST",
                f"/api/review/knowledge/{document.id}/withdraw-approval",
                {"target_status": "pending_review", "reason": REASON},
                token,
            )
            api_results.append(
                {
                    "document_id": str(document.id),
                    "review_record_id": result["data"]["review_record"]["id"],
                    "before_status": result["data"]["review_record"]["before_status"],
                    "after_status": result["data"]["review_record"]["after_status"],
                }
            )

        session.expire_all()
        after = []
        for item in before:
            document_id = UUID(item["document_id"])
            document = session.get(KnowledgeDocument, document_id)
            record = session.scalar(
                select(KnowledgeReviewRecord)
                .where(
                    KnowledgeReviewRecord.document_id == document_id,
                    KnowledgeReviewRecord.review_action == "withdraw_approval",
                )
                .order_by(KnowledgeReviewRecord.created_at.desc())
                .limit(1)
            )
            operation = session.scalar(
                select(OperationLog)
                .where(
                    OperationLog.target_id == str(document_id),
                    OperationLog.action == "withdraw_approval",
                )
                .order_by(OperationLog.created_at.desc())
                .limit(1)
            )
            if not document or not record or not operation:
                raise RuntimeError(f"Missing withdrawal audit evidence for {document_id}")
            metadata = document.metadata_json or {}
            if not (
                document.review_status == "pending_review"
                and record.before_status == "approved"
                and record.after_status == "pending_review"
                and record.reviewer_id == UUID(actor["id"])
                and metadata.get("approved_for_pilot") is False
                and metadata.get("requires_individual_review") is True
                and metadata.get("pilot_index_excluded") is True
                and (operation.detail or {}).get("automatic_operation") is False
            ):
                raise RuntimeError(f"Withdrawal audit invariant failed for {document_id}")
            after.append(
                {
                    "document_id": str(document_id),
                    "review_status": document.review_status,
                    "quality_status": metadata.get("quality_status"),
                    "approved_for_pilot": metadata.get("approved_for_pilot"),
                    "requires_individual_review": metadata.get("requires_individual_review"),
                    "pilot_index_excluded": metadata.get("pilot_index_excluded"),
                    "review_record": {
                        "id": str(record.id),
                        "before_status": record.before_status,
                        "after_status": record.after_status,
                        "reviewer_id": str(record.reviewer_id),
                        "reviewed_at": record.reviewed_at.isoformat(),
                        "reason": record.review_comment,
                        "automatic_operation": (record.metadata_json or {}).get("automatic_operation"),
                    },
                    "operation_log": {
                        "id": str(operation.id),
                        "operator": operation.operator,
                        "created_at": operation.created_at.isoformat(),
                        "before_status": (operation.detail or {}).get("before_status"),
                        "after_status": (operation.detail or {}).get("after_status"),
                        "automatic_operation": (operation.detail or {}).get("automatic_operation"),
                    },
                }
            )

        remaining_official = [
            str(item.id)
            for item in session.scalars(select(KnowledgeDocument).where(KnowledgeDocument.review_status == "approved"))
            if is_vendor_official(item)
        ]
        if set(remaining_official) != {str(item) for item in EXPECTED_APPROVED_IDS}:
            raise RuntimeError(f"Unexpected final approved set: {remaining_official}")

    payload = {
        "task": "Task 25B-R2-U3-R2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "execution_path": "authenticated_review_api_only",
        "direct_database_mutation": False,
        "actor": {"id": actor["id"], "username": actor["username"], "role": actor["role"]},
        "expected_approved_document_ids": sorted(str(item) for item in EXPECTED_APPROVED_IDS),
        "unexpected_approved_count": len(before),
        "before": before,
        "api_results": api_results,
        "after": after,
        "remaining_approved_official_document_ids": sorted(remaining_official),
        "pilot_index_executed": False,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "passed",
        "unexpected_approved_withdrawn": len(after),
        "remaining_expected_approved": len(remaining_official),
        "output": str(OUTPUT_PATH),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
