from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.document_parser import DocumentParser
from app.services.text_splitter import TextSplitter
from app.services.text_vector_service import TextVectorService


TITLE = "华为 SUN2000-196KTL-H0 用户手册 RAG 版"
MANUAL_PATH = Path("storage/samples/huawei_sun2000_196ktl_h0_user_manual_rag.md")
IMAGE_DIR = Path("storage/samples/huawei_sun2000_196ktl_h0_images")


def import_sample_manual() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    manual_path = backend_root / MANUAL_PATH
    image_dir = backend_root / IMAGE_DIR
    if not manual_path.exists():
        raise FileNotFoundError(f"Sample manual not found: {manual_path}")
    if not image_dir.exists():
        raise FileNotFoundError(f"Sample image directory not found: {image_dir}")

    parser = DocumentParser()
    splitter = TextSplitter()
    vectorizer = TextVectorService()
    parsed_document = parser.parse_document(manual_path, "md")
    chunks = splitter.split(parsed_document)
    if not chunks:
        raise RuntimeError("Sample manual generated no chunks")

    db = SessionLocal()
    repository = KnowledgeRepository(db)
    try:
        document = repository.get_document_by_title(TITLE)
        if document:
            repository.delete_chunks_by_document(document.id)
        else:
            document = KnowledgeDocument(
                title=TITLE,
                manufacturer="huawei",
                product_series="SUN2000",
                device_type="pv_inverter",
                document_type="manual",
            )
            document = repository.create_document(document)

        document.manufacturer = "huawei"
        document.product_series = "SUN2000"
        document.model = "SUN2000-196KTL-H0"
        document.device_type = "pv_inverter"
        document.document_type = "manual"
        document.source = "华为逆变器SUN2000-196KTL-H0++用户手册.pdf"
        document.source_type = "sample_manual"
        document.file_name = manual_path.name
        document.file_path = MANUAL_PATH.as_posix()
        document.file_size = manual_path.stat().st_size
        document.file_ext = "md"
        document.page_count = parsed_document.page_count
        document.parse_status = "parsed"
        document.parser_name = parsed_document.metadata.get("parser")
        document.chunk_count = len(chunks)
        document.summary = "华为 SUN2000-196KTL-H0 用户手册，含正文、图片 OCR 与图片说明，用于可追溯 RAG 检索。"
        document.error_message = None
        document.metadata_json = {
            "sample": True,
            "parser_metadata": parsed_document.metadata,
            "parse_warnings": parsed_document.warnings,
            "image_dir": IMAGE_DIR.as_posix(),
            "image_count": len([path for path in image_dir.iterdir() if path.is_file()]),
        }
        document.parsed_at = datetime.now(timezone.utc)
        document.review_status = "approved"
        document.reviewed_at = datetime.now(timezone.utc)
        document.review_comment = "Approved sample document for local RAG testing."
        document.status = "active"
        repository.update_document(document)

        chunk_models = [
            KnowledgeChunk(
                document_id=document.id,
                manufacturer=document.manufacturer,
                product_series=document.product_series,
                device_type=document.device_type,
                document_type=document.document_type,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                content_hash=hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
                section_title=chunk.section_title,
                char_count=chunk.char_count,
                page_number=chunk.page_number,
                embedding_status="embedded",
                metadata_json=vectorizer.metadata_for_text(chunk.content, chunk.metadata),
                status="active",
            )
            for chunk in chunks
        ]
        repository.create_chunks(chunk_models)
        db.commit()
        print(f"Imported sample manual. document_id={document.id}, chunks={len(chunk_models)}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import_sample_manual()
