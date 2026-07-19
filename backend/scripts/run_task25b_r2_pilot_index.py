from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from sqlalchemy import select

from task25b_r2_common import RUNTIME, now_iso, write_json

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeDocument, User
from app.services.vector_index_service import VectorIndexService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--pilot-only", action="store_true")
    parser.add_argument("--approved-only", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    selection_path = RUNTIME / "pilot_document_selection.json"
    collection_path = RUNTIME / "pilot_collection_check.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8")) if selection_path.exists() else {}
    collection = json.loads(collection_path.read_text(encoding="utf-8")) if collection_path.exists() else {}
    reasons = []
    if not (args.allow_real_api and args.pilot_only and args.approved_only):
        reasons.append("all explicit safety flags are required")
    if not (settings.TASK25B_ALLOW_REAL_API and settings.TASK25B_R2_PILOT_ENABLED and settings.TASK25B_R2_ALLOW_PILOT_INDEX):
        reasons.append("Pilot real API gates are not enabled")
    if selection.get("status") != "READY":
        reasons.append(selection.get("status") or "pilot selection is unavailable")
    if collection.get("status") != "PASSED":
        reasons.append(collection.get("status") or "independent Pilot Collection is unavailable")
    selected = selection.get("selected_documents") or []
    eligible = sum(int(item.get("chunk_count") or 0) for item in selected)
    payload = {
        "generated_at": now_iso(),
        "status": "BLOCKED" if reasons else "RUNNING",
        "blocked_reasons": reasons,
        "pilot_collection": settings.DASHVECTOR_PILOT_COLLECTION,
        "base_collection": settings.DASHVECTOR_PHYSICAL_COLLECTION,
        "selected_documents": len(selected),
        "eligible_chunks": eligible,
        "embedded_chunks": 0,
        "cache_hits": 0,
        "upserted_vectors": 0,
        "skipped_vectors": 0,
        "failed_vectors": 0,
        "retry_count": 0,
        "429_count": 0,
        "duration_seconds": 0.0,
        "estimated_cost": None,
        "token_usage": None,
        "full_reindex_performed": False,
        "formal_documents_modified": False,
    }
    failures = []
    if reasons:
        write_json("pilot_index_result.json", payload)
        write_json("pilot_index_failures.json", {"failures": reasons})
        write_json("pilot_index_progress.json", {"status": "BLOCKED", "completed": 0, "total": eligible})
        print(json.dumps(payload, ensure_ascii=False))
        return 2

    started = time.perf_counter()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.role == "admin", User.is_active.is_(True)).order_by(User.created_at))
        if not user:
            raise RuntimeError("An active admin is required for an audited Pilot index run")
        service = VectorIndexService(
            db, allow_real_api=True, collection_name=settings.DASHVECTOR_PILOT_COLLECTION, namespace="default"
        )
        for document_row in selected:
            document = db.get(KnowledgeDocument, document_row["document_id"])
            if not document or not (
                document.review_status == "approved" and document.parse_status == "parsed" and document.status == "active"
            ):
                failures.append({"document_id": document_row["document_id"], "reason": "status_changed"})
                continue
            try:
                result = service.index_document(document.id, current_user=user)
                payload["upserted_vectors"] += result.succeeded_count
                payload["skipped_vectors"] += result.skipped_count
                payload["failed_vectors"] += result.failed_count
            except Exception as exc:
                failures.append({"document_id": str(document.id), "reason": type(exc).__name__})
    payload["embedded_chunks"] = payload["upserted_vectors"]
    payload["duration_seconds"] = round(time.perf_counter() - started, 3)
    payload["status"] = "PASSED" if not failures and payload["failed_vectors"] == 0 else "PARTIAL_FAILED"
    write_json("pilot_index_result.json", payload)
    write_json("pilot_index_failures.json", {"failures": failures})
    write_json("pilot_index_progress.json", {"status": payload["status"], "completed": payload["upserted_vectors"], "total": eligible})
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] == "PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
