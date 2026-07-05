from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models import KnowledgeChunk, KnowledgeDocument, QARecord, User  # noqa: E402
from app.services.embedding_service import EmbeddingService  # noqa: E402
from app.services.vector_index_service import VectorIndexService  # noqa: E402
from scripts.task24c_real_api_common import (  # noqa: E402
    MARKER,
    missing_config,
    print_result,
    provider_config_summary,
    write_result,
)


def _admin_user(db) -> User | None:
    return db.scalar(select(User).where(User.username == "admin"))


def _create_task24c_document(db, marker: str) -> tuple[KnowledgeDocument, KnowledgeChunk]:
    content = (
        f"{marker} Huawei SUN2000 PV inverter alarm troubleshooting content. "
        "When an inverter alarm occurs, confirm DC switch status, AC breaker status, insulation resistance, "
        "grid voltage, fan condition, communication state, and manufacturer safety isolation steps. "
        "All vector retrieval results must remain source traceable and require field engineer confirmation."
    )
    document = KnowledgeDocument(
        title=f"{marker} DashVector real-call PV inverter manual",
        manufacturer="huawei",
        product_series="SUN2000",
        model="SUN2000",
        device_type="pv_inverter",
        document_type="manual",
        source="Task24C_real_dashvector_optional",
        source_type="task24c_online_acceptance",
        file_name=f"{marker}_dashvector_real.txt",
        file_path=None,
        file_size=len(content.encode("utf-8")),
        file_ext="txt",
        page_count=1,
        parse_status="parsed",
        parser_name="task24c_real_optional",
        chunk_count=1,
        summary="Task24C real DashVector/Embedding online acceptance fixture.",
        error_message=None,
        metadata_json={
            "task_marker": marker,
            "real_external_api_target": "dashvector_embedding",
            "not_for_production": True,
        },
        parsed_at=datetime.now(timezone.utc),
        review_status="approved",
        status="active",
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
        section_title="Task24C real vector retrieval fixture",
        char_count=len(content),
        page_number=1,
        embedding_status="pending",
        metadata_json={"task_marker": marker, "not_for_production": True},
        status="active",
    )
    db.add(chunk)
    db.flush()
    document.chunk_count = 1
    return document, chunk


def _write_qa_record(db, *, marker: str, document: KnowledgeDocument, chunk: KnowledgeChunk, hit_count: int, current_user: User | None) -> QARecord:
    trace_id = f"task24c-vector-{uuid4().hex[:20]}"
    reference = {
        "document_id": str(document.id),
        "document_title": document.title,
        "document_type": document.document_type,
        "manufacturer": document.manufacturer,
        "product_series": document.product_series,
        "device_type": document.device_type,
        "section_title": chunk.section_title,
        "chunk_index": chunk.chunk_index,
        "source": document.source,
        "retrieval_mode": "vector",
        "real_external_api_used": True,
    }
    record = QARecord(
        question=f"{marker} How should an engineer troubleshoot a Huawei SUN2000 inverter alarm?",
        normalized_query=f"{marker} SUN2000 inverter alarm troubleshooting",
        manufacturer=document.manufacturer,
        product_series=document.product_series,
        device_type=document.device_type,
        document_type=document.document_type,
        answer=(
            "Task24C vector online acceptance wrote this QA record after real embedding and DashVector query. "
            "The answer remains an acceptance artifact, not production maintenance advice."
        ),
        references=[reference],
        retrieved_chunks=[{**reference, "chunk_id": str(chunk.id), "content_preview": chunk.content[:240]}],
        suggested_steps=["Safety isolation", "Alarm confirmation", "DC/AC status check", "Record trace evidence"],
        safety_notes=["Follow Huawei/Sungrow PV inverter electrical safety procedures before field action."],
        related_history=[],
        model_provider="dashvector",
        model_name=get_settings().EMBEDDING_MODEL,
        confidence=0.66 if hit_count else 0.2,
        trace_id=trace_id,
        created_by=current_user.id if current_user else None,
    )
    db.add(record)
    db.flush()
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Optional real DashVector + embedding acceptance check.")
    parser.add_argument("--allow-real-api", action="store_true", help="Actually call embedding and DashVector providers.")
    args = parser.parse_args()
    marker = MARKER
    if not args.allow_real_api:
        result = {
            "provider": "dashvector_embedding",
            "status": "skipped",
            "reason": "real DashVector/Embedding check requires --allow-real-api",
            "real_external_api_used": False,
            "config": provider_config_summary(),
        }
        write_result("dashvector_real_result.json", result)
        print_result(result)
        return 0

    missing = missing_config("dashvector")
    if missing:
        result = {
            "provider": "dashvector_embedding",
            "status": "blocked",
            "missing_or_invalid": missing,
            "real_external_api_used": False,
            "config": provider_config_summary(),
        }
        write_result("dashvector_real_result.json", result)
        print_result(result)
        return 0

    with SessionLocal() as db:
        current_user = _admin_user(db)
        document, chunk = _create_task24c_document(db, marker)
        service = VectorIndexService(db, allow_real_api=True)
        index_result = service.index_document(document.id, current_user=current_user, force=True)
        query_result = service.test_query(
            f"{marker} SUN2000 inverter alarm troubleshooting insulation resistance AC DC",
            top_k=5,
            filters={"manufacturer": "huawei", "product_series": "SUN2000", "device_type": "pv_inverter", "document_type": "manual"},
        )
        hit_ids = [str(item.chunk_id) for item in query_result.hits]
        verified = str(chunk.id) in hit_ids
        qa_record = _write_qa_record(
            db,
            marker=marker,
            document=document,
            chunk=chunk,
            hit_count=len(query_result.hits),
            current_user=current_user,
        )
        document_id = str(document.id)
        chunk_id = str(chunk.id)
        index_run_id = str(index_result.run.id)
        qa_trace_id = qa_record.trace_id
        db.commit()

    result = {
        "provider": "dashvector_embedding",
        "status": "passed" if verified else "failed",
        "real_external_api_used": True,
        "marker": marker,
        "document_id": document_id,
        "chunk_id": chunk_id,
        "index_run_id": index_run_id,
        "processed": index_result.processed,
        "succeeded": index_result.succeeded,
        "failed": index_result.failed,
        "vector_backend": query_result.vector_backend,
        "embedding_provider": query_result.embedding_provider,
        "embedding_model": query_result.embedding_model,
        "embedding_dimension": query_result.embedding_dimension,
        "query_hit_count": len(query_result.hits),
        "verified_task_chunk_hit": verified,
        "qa_record_trace_id": qa_trace_id,
        "qa_record_retrieval_mode": "vector",
        "fallback": "keyword retrieval remains available through normal retrieval service",
        "config": provider_config_summary(),
    }
    write_result("dashvector_real_result.json", result)
    print_result(result)
    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
