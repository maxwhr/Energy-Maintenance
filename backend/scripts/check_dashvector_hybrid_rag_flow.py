from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import KnowledgeChunk, KnowledgeDocument, QARecord, User  # noqa: E402
from app.schemas.retrieval import RetrievalQueryRequest  # noqa: E402
from app.services.embedding_service import EmbeddingService  # noqa: E402
from app.services.retrieval_service import RetrievalService  # noqa: E402
from app.services.vector_index_service import VectorIndexService  # noqa: E402

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover
    TestClient = None


class CheckError(AssertionError):
    pass


RUN_ID = time.strftime("%Y%m%d%H%M%S")
MARKER = f"Task24B_DashVector_{RUN_ID}"
PASSWORD = "Task24B_pass123"


def ensure_user(db, role: str) -> User:
    username = f"{MARKER}_{role}"
    user = db.scalar(select(User).where(User.username == username))
    if user:
        return user
    user = User(
        username=username,
        password_hash=hash_password(PASSWORD),
        display_name=f"{MARKER} {role}",
        role=role,
        status="active",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_document(db, *, title: str, review_status: str, status: str, content: str) -> KnowledgeDocument:
    document = KnowledgeDocument(
        title=title,
        manufacturer="huawei",
        product_series="SUN2000",
        device_type="pv_inverter",
        document_type="manual",
        source=f"{MARKER}_local_fixture",
        source_type="script_fixture",
        parse_status="parsed",
        chunk_count=1,
        review_status=review_status,
        status=status,
        summary=content[:180],
        metadata_json={"marker": MARKER, "purpose": "dashvector_hybrid_rag_flow"},
    )
    db.add(document)
    db.flush()
    chunk = KnowledgeChunk(
        document_id=document.id,
        manufacturer=document.manufacturer,
        product_series=document.product_series,
        device_type=document.device_type,
        document_type=document.document_type,
        chunk_index=0,
        content=content,
        content_hash=EmbeddingService.content_hash(content),
        section_title="SUN2000 insulation alarm inspection",
        char_count=len(content),
        embedding_status="pending",
        status="active",
        metadata_json={"marker": MARKER},
    )
    db.add(chunk)
    db.commit()
    db.refresh(document)
    return document


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def check_viewer_forbidden(document_id: str, viewer: User) -> None:
    token, _ = create_access_token(str(viewer.id))
    if TestClient is None:
        base_url = os.getenv("BASE_URL") or os.getenv("TASK24B_BASE_URL")
        if not base_url:
            print("[skipped] viewer route permission: TestClient unavailable and BASE_URL not set")
            return
        payload = json.dumps(
            {"vector_backend": "fake_in_memory", "provider": "deterministic_test", "force": True}
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{base_url.rstrip('/')}/api/vector-search/documents/{document_id}/index",
            data=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - local acceptance URL only
                status_code = response.status
        except urllib.error.HTTPError as exc:
            status_code = exc.code
        assert_true(status_code in {401, 403}, f"viewer should not trigger vector index, got {status_code}")
        return
    client = TestClient(app)
    response = client.post(
        f"/api/vector-search/documents/{document_id}/index",
        headers={"Authorization": f"Bearer {token}"},
        json={"vector_backend": "fake_in_memory", "provider": "deterministic_test", "force": True},
    )
    assert_true(response.status_code in {401, 403}, f"viewer should not trigger vector index, got {response.status_code}")


def main() -> int:
    with SessionLocal() as db:
        expert = ensure_user(db, "expert")
        viewer = ensure_user(db, "viewer")
        approved = create_document(
            db,
            title=f"{MARKER} approved SUN2000 manual",
            review_status="approved",
            status="active",
            content="华为 SUN2000 光伏逆变器出现绝缘告警后，应先停机确认安全，检查组串绝缘电阻、直流端子受潮、接地线和告警代码，并记录排查过程。",
        )
        pending = create_document(
            db,
            title=f"{MARKER} pending SUN2000 manual",
            review_status="pending_review",
            status="active",
            content="待审核资料：逆变器绝缘告警排查内容不应进入检索结果。",
        )
        archived = create_document(
            db,
            title=f"{MARKER} archived SUN2000 manual",
            review_status="approved",
            status="active",
            content="归档资料：逆变器绝缘告警排查内容不应进入检索结果。",
        )
        vector_service = VectorIndexService(db)
        for document in (approved, pending, archived):
            vector_service.index_document(
                document.id,
                current_user=expert,
                provider="deterministic_test",
                vector_backend="fake_in_memory",
                force=True,
            )
        archived.status = "archived"
        db.add(archived)
        db.commit()

        response = RetrievalService(db).query(
            RetrievalQueryRequest(
                query="华为 SUN2000 逆变器绝缘告警如何排查",
                manufacturer="huawei",
                product_series="SUN2000",
                device_type="pv_inverter",
                document_type="manual",
                retrieval_mode="hybrid",
                enable_vector=True,
                top_k=5,
                vector_top_k=8,
                min_score=0.05,
            ),
            current_user=expert,
        )
        assert_true(response.references, "hybrid retrieval should return approved references")
        returned_document_ids = {str(item.document_id) for item in response.retrieved_chunks}
        assert_true(str(approved.id) in returned_document_ids, "approved document must be returned")
        assert_true(str(pending.id) not in returned_document_ids, "pending_review document must not be returned")
        assert_true(str(archived.id) not in returned_document_ids, "archived document must not be returned")
        assert_true(any(item.vector_score is not None for item in response.retrieved_chunks), "vector_score should be present")
        assert_true(response.retrieval_mode in {"hybrid", "keyword"}, "retrieval_mode should be explicit")
        qa = db.scalar(select(QARecord).where(QARecord.trace_id == response.trace_id))
        assert_true(qa is not None, "qa_records should contain retrieval trace")
        history_json = json.dumps(qa.related_history or [], ensure_ascii=False)
        assert_true("retrieval_mode" in history_json, "qa_records should store retrieval diagnostics")

        fallback = RetrievalService(db).query(
            RetrievalQueryRequest(
                query="逆变器绝缘告警排查",
                manufacturer="huawei",
                product_series="SUN2000",
                device_type="pv_inverter",
                document_type="manual",
                retrieval_mode="vector",
                enable_vector=False,
                top_k=3,
            ),
            current_user=expert,
        )
        assert_true(fallback.vector_fallback_used, "vector disabled should fallback to keyword")
        assert_true(fallback.references, "keyword fallback should still return references")
        check_viewer_forbidden(str(approved.id), viewer)

    result = {
        "status": "passed",
        "marker": MARKER,
        "approved_document_id": str(approved.id),
        "references": len(response.references),
        "retrieved_chunks": len(response.retrieved_chunks),
        "trace_id": response.trace_id,
        "vector_backend": response.vector_backend,
        "real_external_call": False,
        "raw_vectors_returned": False,
        "delivery_zip_created": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "failed", "error": str(exc), "real_external_call": False}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
