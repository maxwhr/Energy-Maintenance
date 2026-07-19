from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import UploadedMedia
from app.repositories.media_repository import MediaRepository
from app.schemas.media import MediaOCRResponse, OCRResult, OCRStatusResponse
from app.services.ocr_adapters import TesseractOCRAdapter


SUPPORTED_OCR_PROVIDERS = {"tesseract"}
SUPPORTED_OCR_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


class OCRServiceError(ValueError):
    pass


class OCRService:
    def __init__(self, db: Session | None = None):
        self.db = db
        self.repository = MediaRepository(db) if db else None
        self.settings = get_settings()

    def get_status(self) -> OCRStatusResponse:
        provider = self.settings.OCR_PROVIDER.strip().lower()
        base = {
            "enabled": self.settings.OCR_ENABLED,
            "provider": provider,
            "lang": self.settings.OCR_LANG,
            "command": Path(self.settings.OCR_TESSERACT_CMD).name or "tesseract",
            "timeout_seconds": self.settings.OCR_TIMEOUT_SECONDS,
            "max_image_mb": self.settings.OCR_MAX_IMAGE_MB,
        }
        if not self.settings.OCR_ENABLED:
            return OCRStatusResponse(
                **base,
                status="disabled",
                available=False,
                message="OCR is disabled",
                metadata={"reason": "OCR_ENABLED=false"},
            )
        if provider not in SUPPORTED_OCR_PROVIDERS:
            return OCRStatusResponse(
                **base,
                status="not_configured",
                available=False,
                message="Unsupported OCR provider",
                error_summary=f"Unsupported provider: {provider}",
            )
        availability = self._adapter().check_availability()
        return OCRStatusResponse(
            **base,
            status=availability.status,
            available=availability.available,
            message=availability.message,
            error_summary=availability.error_summary,
            metadata=availability.metadata,
        )

    def extract_text(self, file_path: str) -> OCRResult:
        status = self.get_status()
        if status.status != "available":
            return OCRResult(
                status=status.status,
                text="",
                message=status.message,
                error_summary=status.error_summary,
                metadata=status.metadata,
            )
        result = self._adapter().recognize_image(
            file_path,
            lang=self.settings.OCR_LANG,
            timeout=self.settings.OCR_TIMEOUT_SECONDS,
        )
        return OCRResult(
            status=result.status,
            text=result.text,
            message=result.message,
            error_summary=result.error_summary,
            metadata=result.metadata,
        )

    def recognize_media(self, media_id: UUID) -> MediaOCRResponse:
        media = self._get_media(media_id)
        status = self.get_status()
        if status.status != "available":
            self._update_media_ocr(
                media,
                status=status.status,
                text="",
                message=status.message,
                error_summary=status.error_summary,
                metadata=status.metadata,
                processed_at=None,
            )
            return self._response_from_media(media)

        self._validate_media(media)
        media_path = self._resolve_file_path(media)
        result = self.extract_text(str(media_path))
        processed_at = datetime.now(timezone.utc).isoformat() if result.status == "processed" else None
        self._update_media_ocr(
            media,
            status=result.status,
            text=result.text,
            message=result.message,
            error_summary=result.error_summary,
            metadata=result.metadata,
            processed_at=processed_at,
        )
        return self._response_from_media(media)

    def get_media_ocr(self, media_id: UUID) -> MediaOCRResponse:
        media = self._get_media(media_id)
        return self._response_from_media(media)

    def _update_media_ocr(
        self,
        media: UploadedMedia,
        *,
        status: str,
        text: str,
        message: str,
        error_summary: str | None,
        metadata: dict,
        processed_at: str | None,
    ) -> None:
        metadata_json = dict(media.metadata_json or {})
        ocr_payload = {
            "status": status,
            "provider": self.settings.OCR_PROVIDER,
            "lang": self.settings.OCR_LANG,
            "text": text,
            "processed_at": processed_at,
            "error_summary": error_summary,
            "message": message,
            "metadata": metadata,
        }
        metadata_json["ocr"] = ocr_payload
        metadata_json["ocr_status"] = status
        metadata_json["ocr_message"] = message
        metadata_json["ocr_error_summary"] = error_summary
        metadata_json["ocr_processed_at"] = processed_at
        metadata_json["ocr_metadata"] = metadata
        media.ocr_text = text or None
        media.metadata_json = metadata_json
        if self.db:
            try:
                self.db.add(media)
                self.db.commit()
                self.db.refresh(media)
            except SQLAlchemyError as exc:
                self.db.rollback()
                raise OCRServiceError(f"OCR metadata write failed: {exc}") from exc

    def _response_from_media(self, media: UploadedMedia) -> MediaOCRResponse:
        metadata = media.metadata_json or {}
        ocr = metadata.get("ocr") if isinstance(metadata.get("ocr"), dict) else {}
        return MediaOCRResponse(
            media_id=media.id,
            status=str(ocr.get("status") or metadata.get("ocr_status") or "disabled"),
            provider=str(ocr.get("provider") or self.settings.OCR_PROVIDER),
            lang=str(ocr.get("lang") or self.settings.OCR_LANG),
            text=str(ocr.get("text") or media.ocr_text or ""),
            message=str(ocr.get("message") or metadata.get("ocr_message") or "OCR is disabled"),
            error_summary=ocr.get("error_summary") or metadata.get("ocr_error_summary"),
            processed_at=ocr.get("processed_at") or metadata.get("ocr_processed_at"),
            metadata=ocr.get("metadata") or metadata.get("ocr_metadata") or {},
        )

    def _get_media(self, media_id: UUID) -> UploadedMedia:
        if not self.repository:
            raise OCRServiceError("OCRService requires a database session")
        media = self.repository.get_by_id(media_id)
        if not media:
            raise OCRServiceError("Media item not found")
        return media

    def _validate_media(self, media: UploadedMedia) -> None:
        file_ext = (media.file_ext or "").lower()
        if file_ext not in SUPPORTED_OCR_IMAGE_EXTENSIONS:
            raise OCRServiceError("Only jpg, jpeg, png, and webp media can be processed by OCR")
        max_bytes = self.settings.OCR_MAX_IMAGE_MB * 1024 * 1024
        if media.file_size and media.file_size > max_bytes:
            raise OCRServiceError(f"OCR image exceeds {self.settings.OCR_MAX_IMAGE_MB}MB limit")

    def _resolve_file_path(self, media: UploadedMedia) -> Path:
        stored_path = Path(media.file_path)
        path = stored_path.resolve() if stored_path.is_absolute() else (self._backend_root() / stored_path).resolve()
        upload_dir = self._media_upload_dir()
        try:
            path.relative_to(upload_dir)
        except ValueError as exc:
            raise OCRServiceError("Unsafe media storage path") from exc
        if not path.is_file():
            raise OCRServiceError("Media file is missing from storage")
        return path

    def _media_upload_dir(self) -> Path:
        base = Path(self.settings.UPLOAD_DIR)
        if not base.is_absolute():
            base = self._backend_root() / base
        return (base / "media").resolve()

    def _adapter(self) -> TesseractOCRAdapter:
        return TesseractOCRAdapter(
            command=self.settings.OCR_TESSERACT_CMD,
            lang=self.settings.OCR_LANG,
        )

    @staticmethod
    def _backend_root() -> Path:
        return Path(__file__).resolve().parents[2]
