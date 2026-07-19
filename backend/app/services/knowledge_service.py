from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import KnowledgeChunk, KnowledgeDocument, User
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.knowledge import KnowledgeDocumentCreate
from app.services.document_parser import DocumentParser, DocumentParserError
from app.services.semantic_chunker import SemanticChunker
from app.services.candidate_hydration_service import CandidateHydrationService


ALLOWED_MANUFACTURERS = {"huawei", "sungrow"}
ALLOWED_PRODUCT_SERIES = {"SUN2000", "FusionSolar", "SG"}
ALLOWED_DEVICE_TYPES = {"pv_inverter"}
ALLOWED_DOCUMENT_TYPES = {
    "manual",
    "alarm_code",
    "sop",
    "fault_case",
    "inspection_standard",
    "maintenance_record",
}


class KnowledgeServiceError(ValueError):
    pass


@dataclass
class StoredFile:
    original_file_name: str
    file_name: str
    file_path: str
    file_ext: str
    file_size: int
    mime_type: str | None = None


class KnowledgeService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = KnowledgeRepository(db)
        self.settings = get_settings()
        self.parser = DocumentParser()
        self.splitter = SemanticChunker(
            chunk_size=self.settings.DEFAULT_CHUNK_SIZE,
            overlap=self.settings.DEFAULT_CHUNK_OVERLAP,
        )

    async def upload_and_process_document(
        self,
        *,
        file: UploadFile,
        title: str | None,
        manufacturer: str,
        product_series: str,
        device_type: str,
        document_type: str,
        description: str | None,
        source: str | None,
        current_user: User,
    ) -> dict:
        self._validate_domain(
            manufacturer=manufacturer,
            product_series=product_series,
            device_type=device_type,
            document_type=document_type,
        )
        stored_file = await self._store_upload(file, "documents")
        document_title = (title or Path(stored_file.original_file_name).stem).strip()
        if not document_title:
            raise KnowledgeServiceError("Document title must not be empty")

        document = KnowledgeDocument(
            title=document_title,
            manufacturer=manufacturer,
            product_series=product_series,
            device_type=device_type,
            document_type=document_type,
            source=source or "user_upload",
            source_type="user_upload",
            file_name=stored_file.file_name,
            file_path=stored_file.file_path,
            file_size=stored_file.file_size,
            file_ext=stored_file.file_ext,
            parse_status="processing",
            parser_name=None,
            chunk_count=0,
            summary=description,
            error_message=None,
            metadata_json={
                "original_file_name": stored_file.original_file_name,
                "mime_type": stored_file.mime_type,
            },
            review_status="pending_review",
            submitted_by=current_user.id,
            status="active",
        )

        try:
            document = self.repository.create_document(document)
            self.db.commit()
            self.db.refresh(document)
        except SQLAlchemyError as exc:
            self.db.rollback()
            self._remove_unreferenced_stored_file(stored_file)
            raise KnowledgeServiceError(f"Database write failed: {exc}") from exc

        try:
            result = self._parse_and_replace_chunks(document)
            self.db.commit()
            CandidateHydrationService.invalidate_scope_cache()
            return result
        except (DocumentParserError, KnowledgeServiceError) as exc:
            self.db.rollback()
            self._mark_document_failed(document, str(exc))
            raise KnowledgeServiceError(f"Document parse failed: {exc}") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            self._mark_document_failed(document, str(exc))
            raise KnowledgeServiceError(f"Database write failed: {exc}") from exc

    def list_documents(
        self,
        *,
        manufacturer: str | None = None,
        product_series: str | None = None,
        device_type: str | None = None,
        document_type: str | None = None,
        parse_status: str | None = None,
        review_status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        self._validate_page(page, page_size)
        documents, total = self.repository.list_documents(
            manufacturer=manufacturer,
            product_series=product_series,
            device_type=device_type,
            document_type=document_type,
            parse_status=parse_status,
            review_status=review_status,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return {
            "items": documents,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_document(self, document_id: UUID) -> KnowledgeDocument | None:
        return self.repository.get_document(document_id)

    def list_document_chunks(
        self,
        document_id: UUID,
        *,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        self._validate_page(page, page_size)
        document = self.repository.get_document(document_id)
        if not document:
            raise KnowledgeServiceError("Knowledge document not found")
        chunks, total = self.repository.list_chunks_by_document(
            document_id=document_id,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return {
            "items": chunks,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def reparse_document(self, document_id: UUID) -> dict:
        document = self.repository.get_document(document_id)
        if not document:
            raise KnowledgeServiceError("Knowledge document not found")
        if not document.file_path:
            raise KnowledgeServiceError("Document file path is empty")
        if not Path(document.file_path).is_absolute():
            file_path = self._backend_root() / document.file_path
        else:
            file_path = Path(document.file_path)
        if not file_path.exists():
            self._mark_document_failed(document, "Uploaded document file does not exist")
            raise KnowledgeServiceError("Uploaded document file does not exist")

        try:
            document.parse_status = "processing"
            document.error_message = None
            document.chunk_count = 0
            self.repository.update_document(document)
            result = self._parse_and_replace_chunks(document)
            self.db.commit()
            CandidateHydrationService.invalidate_scope_cache()
            return result
        except (DocumentParserError, KnowledgeServiceError) as exc:
            self.db.rollback()
            self._mark_document_failed(document, str(exc))
            raise KnowledgeServiceError(f"Document reparse failed: {exc}") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise KnowledgeServiceError(f"Database write failed: {exc}") from exc

    def archive_document(self, document_id: UUID) -> KnowledgeDocument:
        document = self.repository.get_document(document_id)
        if not document:
            raise KnowledgeServiceError("Knowledge document not found")
        document.status = "archived"
        document.review_status = "archived"
        self.repository.archive_chunks_by_document(document.id)
        document = self.repository.update_document(document)
        self.db.commit()
        CandidateHydrationService.invalidate_scope_cache()
        return document

    def create_document_metadata(self, payload: KnowledgeDocumentCreate) -> KnowledgeDocument:
        self._validate_domain(
            manufacturer=payload.manufacturer,
            product_series=payload.product_series or "",
            device_type=payload.device_type,
            document_type=payload.document_type,
        )
        document = KnowledgeDocument(**payload.model_dump())
        document = self.repository.create_document(document)
        self.db.commit()
        CandidateHydrationService.invalidate_scope_cache()
        return document

    def _parse_and_replace_chunks(self, document: KnowledgeDocument) -> dict:
        if not document.file_path or not document.file_ext:
            raise KnowledgeServiceError("Document file information is incomplete")

        file_path = Path(document.file_path)
        if not file_path.is_absolute():
            file_path = self._backend_root() / file_path

        parsed_document = self.parser.parse_document(file_path, document.file_ext)
        chunks = self.splitter.split(parsed_document)
        if not chunks:
            raise KnowledgeServiceError("Parsed document generated no knowledge chunks")

        self.repository.delete_chunks_by_document(document.id)
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
                embedding_status="pending",
                metadata_json=chunk.metadata,
                status="active",
            )
            for chunk in chunks
        ]
        self.repository.create_chunks(chunk_models)

        metadata = dict(document.metadata_json or {})
        metadata.update(
            {
                "parser_metadata": parsed_document.metadata,
                "parse_warnings": parsed_document.warnings,
            }
        )
        document.parse_status = "parsed"
        document.parser_name = parsed_document.metadata.get("parser")
        document.page_count = parsed_document.page_count
        document.chunk_count = len(chunk_models)
        document.error_message = None
        document.metadata_json = metadata
        document.parsed_at = datetime.now(timezone.utc)
        self.repository.update_document(document)
        return {
            "document": document,
            "chunk_count": len(chunk_models),
            "parse_status": document.parse_status,
            "warnings": parsed_document.warnings,
        }

    async def _store_upload(self, file: UploadFile, category: str) -> StoredFile:
        original_name = Path(file.filename or "").name
        if not original_name:
            raise KnowledgeServiceError("Uploaded file name is empty")
        safe_original_name = self._safe_name(original_name)
        file_ext = Path(safe_original_name).suffix.lower().lstrip(".")
        if file_ext not in self.settings.allowed_document_extensions:
            raise KnowledgeServiceError(f"Unsupported document extension: {file_ext}")

        content = await file.read()
        if not content:
            raise KnowledgeServiceError("Uploaded file is empty")
        max_bytes = self.settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(content) > max_bytes:
            raise KnowledgeServiceError(f"Uploaded file exceeds {self.settings.MAX_UPLOAD_SIZE_MB}MB limit")

        upload_dir = self._safe_upload_dir(category)
        target_dir = upload_dir / datetime.now(timezone.utc).strftime("%Y%m%d")
        target_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid4().hex}.{file_ext}"
        target_path = (target_dir / stored_name).resolve()
        self._ensure_inside_upload_dir(target_path, upload_dir)
        target_path.write_bytes(content)
        return StoredFile(
            original_file_name=safe_original_name,
            file_name=stored_name,
            file_path=str(target_path.relative_to(self._backend_root()).as_posix()),
            file_ext=file_ext,
            file_size=len(content),
            mime_type=file.content_type,
        )

    def _safe_upload_dir(self, category: str) -> Path:
        base = Path(self.settings.UPLOAD_DIR)
        if not base.is_absolute():
            base = self._backend_root() / base
        upload_dir = (base / category).resolve()
        frontend_dir = (self._backend_root().parent / "frontend").resolve()
        try:
            upload_dir.relative_to(frontend_dir)
            raise KnowledgeServiceError("Upload directory must not be under frontend")
        except ValueError:
            pass
        upload_dir.mkdir(parents=True, exist_ok=True)
        return upload_dir

    def _ensure_inside_upload_dir(self, path: Path, upload_dir: Path) -> None:
        try:
            path.relative_to(upload_dir.resolve())
        except ValueError as exc:
            raise KnowledgeServiceError("Unsafe upload path") from exc

    @staticmethod
    def _safe_name(file_name: str) -> str:
        name = Path(file_name).name.strip()
        name = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "_", name)
        if name in {"", ".", ".."}:
            raise KnowledgeServiceError("Uploaded file name is invalid")
        return name[:180]

    @staticmethod
    def _validate_domain(
        *,
        manufacturer: str,
        product_series: str,
        device_type: str,
        document_type: str,
    ) -> None:
        if manufacturer not in ALLOWED_MANUFACTURERS:
            raise KnowledgeServiceError("Invalid manufacturer")
        if product_series not in ALLOWED_PRODUCT_SERIES:
            raise KnowledgeServiceError("Invalid product_series")
        if device_type not in ALLOWED_DEVICE_TYPES:
            raise KnowledgeServiceError("Invalid device_type")
        if document_type not in ALLOWED_DOCUMENT_TYPES:
            raise KnowledgeServiceError("Invalid document_type")

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise KnowledgeServiceError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise KnowledgeServiceError("page_size must be between 1 and 100")

    def _mark_document_failed(self, document: KnowledgeDocument, error_message: str) -> None:
        try:
            managed = self.repository.get_document(document.id, include_archived=True)
            if not managed:
                return
            self.repository.delete_chunks_by_document(managed.id)
            managed.parse_status = "failed"
            managed.chunk_count = 0
            managed.error_message = error_message
            metadata = dict(managed.metadata_json or {})
            metadata["last_parse_error"] = error_message
            managed.metadata_json = metadata
            self.repository.update_document(managed)
            self.db.commit()
            CandidateHydrationService.invalidate_scope_cache()
        except SQLAlchemyError:
            self.db.rollback()

    def _remove_unreferenced_stored_file(self, stored_file: StoredFile) -> None:
        try:
            candidate = (self._backend_root() / stored_file.file_path).resolve()
            upload_root = Path(self.settings.UPLOAD_DIR)
            if not upload_root.is_absolute():
                upload_root = self._backend_root() / upload_root
            candidate.relative_to(upload_root.resolve())
            candidate.unlink(missing_ok=True)
        except (OSError, ValueError):
            # The database error remains authoritative; never broaden cleanup outside uploads.
            return

    @staticmethod
    def _backend_root() -> Path:
        return Path(__file__).resolve().parents[2]
