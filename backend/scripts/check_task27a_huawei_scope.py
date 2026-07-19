from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import func, select, text


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal, engine  # noqa: E402
from app.models import KnowledgeChunk, KnowledgeDocument, QARecord  # noqa: E402
from app.schemas.retrieval_scope import HUAWEI_SUN2000_COMPETITION_SCOPE_ID  # noqa: E402
from app.services.retrieval_scope_service import RetrievalScopeService  # noqa: E402


def _inclusion_reason(document: KnowledgeDocument) -> str:
    if document.source_type in RetrievalScopeService.OFFICIAL_SOURCE_TYPES:
        return "approved current Chinese Huawei SUN2000/FusionSolar official source"
    return "approved current Chinese Huawei inverter contribution with explicit competition or human review"


def build_inventory() -> dict:
    with SessionLocal() as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        scope = RetrievalScopeService(db).resolve(
            HUAWEI_SUN2000_COMPETITION_SCOPE_ID,
            pilot_required=True,
        )
        rows = list(db.execute(
            select(KnowledgeDocument, func.count(KnowledgeChunk.id))
            .outerjoin(
                KnowledgeChunk,
                (KnowledgeChunk.document_id == KnowledgeDocument.id)
                & (KnowledgeChunk.status == scope.required_chunk_status),
            )
            .where(KnowledgeDocument.id.in_(scope.allowed_document_ids))
            .group_by(KnowledgeDocument.id)
            .order_by(KnowledgeDocument.title, KnowledgeDocument.id)
        )) if scope.allowed_document_ids else []
        documents = []
        for document, chunk_count in rows:
            metadata = dict(document.metadata_json or {})
            documents.append({
                "document_id": str(document.id),
                "title": document.title,
                "manufacturer": document.manufacturer,
                "product_family": document.product_series or metadata.get("product_family"),
                "model": document.model,
                "language": metadata.get("normalized_language"),
                "source_type": document.source_type,
                "review_status": document.review_status,
                "status": document.status,
                "parse_status": document.parse_status,
                "chunk_count": int(chunk_count or 0),
                "inclusion_reason": _inclusion_reason(document),
            })
        safety_counts = {
            "knowledge_documents": int(db.scalar(select(func.count()).select_from(KnowledgeDocument)) or 0),
            "knowledge_chunks": int(db.scalar(select(func.count()).select_from(KnowledgeChunk)) or 0),
            "qa_records": int(db.scalar(select(func.count()).select_from(QARecord)) or 0),
        }
        result = {
            "database_name": engine.url.database,
            "read_only": True,
            "scope_id": scope.scope_id,
            "document_count": len(documents),
            "active_chunk_count": sum(item["chunk_count"] for item in documents),
            "documents": documents,
            "database_safety_counts": safety_counts,
        }
        db.rollback()
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Task 27A Huawei SUN2000 scope inventory")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()
    result = build_inventory()
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
