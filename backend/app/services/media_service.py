from __future__ import annotations

import hashlib
import io
import re
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import UploadedMedia, User
from app.repositories.media_repository import MediaRepository
from app.schemas.media import MediaContextItem
from app.services.ocr_service import OCRService
from app.services.ocr_adapters.base import OCRRecognitionResult


ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_MEDIA_TYPES = {
    "fault_image", "nameplate", "alarm_screen", "indicator_light", "platform_screenshot",
    "site_photo", "inspection_photo", "other",
}
ALLOWED_MANUFACTURERS = {"huawei", "sungrow"}
ALLOWED_PRODUCT_SERIES = {"SUN2000", "FusionSolar", "LUNA2000", "SmartLogger", "SG"}
ALLOWED_DEVICE_TYPES = {"pv_inverter", "battery_system", "smart_logger", "monitoring_platform", "unknown"}
IMAGE_FORMAT_RULES = {
    "JPEG": ({"jpg", "jpeg"}, "image/jpeg"),
    "PNG": ({"png"}, "image/png"),
    "WEBP": ({"webp"}, "image/webp"),
}


class MediaServiceError(ValueError):
    pass


@dataclass
class StoredMediaFile:
    original_file_name: str
    file_name: str
    file_path: str
    file_ext: str
    file_size: int
    mime_type: str | None = None
    source_sha256: str = ""
    stored_sha256: str = ""
    width: int = 0
    height: int = 0
    detected_format: str = ""
    original_orientation: int | None = None
    exif_removed: bool = True


class MediaService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = MediaRepository(db)
        self.settings = get_settings()
        self.ocr_service = OCRService()

    async def upload_media(
        self,
        *,
        file: UploadFile,
        media_type: str,
        description: str | None,
        manufacturer: str | None,
        product_series: str | None,
        device_type: str,
        device_id: UUID | None,
        task_id: UUID | None,
        fault_type: str | None,
        alarm_code: str | None,
        current_user: User,
    ) -> dict:
        self._validate_media_type(media_type)
        self._validate_domain(manufacturer, product_series, device_type)

        if device_id:
            device = self.repository.get_device(device_id)
            if not device:
                raise MediaServiceError("Device not found")
            if device.device_type not in ALLOWED_DEVICE_TYPES:
                raise MediaServiceError("Bound device type is not supported by multimodal maintenance")
            manufacturer = device.manufacturer
            product_series = device.product_series
            device_type = device.device_type
        if task_id and not self.repository.get_task(task_id):
            raise MediaServiceError("Maintenance task not found")

        description = self._clean_metadata_text(description, 2000)
        fault_type = self._clean_metadata_text(fault_type, 64)
        alarm_code = self._clean_metadata_text(alarm_code, 64)
        stored_file = await self._store_upload(file)
        duplicate = self.repository.get_by_source_hash(stored_file.source_sha256, current_user.id)
        if duplicate is not None:
            self._delete_stored_file(stored_file.file_path)
            return {
                "media": duplicate,
                "ocr": self._ocr_result_from_media(duplicate),
                "deduplicated": True,
            }
        ocr_result = self.ocr_service.extract_text(stored_file.file_path)
        ocr_metadata = {
            "status": ocr_result.status,
            "provider": self.settings.OCR_PROVIDER,
            "lang": self.settings.OCR_LANG,
            "text": ocr_result.text,
            "processed_at": datetime.now(timezone.utc).isoformat() if ocr_result.status == "processed" else None,
            "error_summary": ocr_result.error_summary,
            "message": ocr_result.message,
            "metadata": ocr_result.metadata,
        }

        media = UploadedMedia(
            file_name=stored_file.file_name,
            original_file_name=stored_file.original_file_name,
            file_path=stored_file.file_path,
            file_ext=stored_file.file_ext,
            mime_type=stored_file.mime_type,
            file_size=stored_file.file_size,
            media_type=media_type,
            description=description,
            ocr_text=ocr_result.text,
            manufacturer=manufacturer,
            product_series=product_series,
            device_type=device_type,
            device_id=device_id,
            task_id=task_id,
            uploaded_by=current_user.id,
            status="uploaded",
            metadata_json={
                "fault_type": fault_type,
                "alarm_code": alarm_code,
                "ocr": ocr_metadata,
                "ocr_status": ocr_result.status,
                "ocr_message": ocr_result.message,
                "ocr_error_summary": ocr_result.error_summary,
                "ocr_processed_at": ocr_metadata["processed_at"],
                "ocr_metadata": ocr_result.metadata,
                "source_sha256": stored_file.source_sha256,
                "stored_sha256": stored_file.stored_sha256,
                "image_width": stored_file.width,
                "image_height": stored_file.height,
                "image_pixels": stored_file.width * stored_file.height,
                "detected_format": stored_file.detected_format,
                "original_orientation": stored_file.original_orientation,
                "exif_removed": stored_file.exif_removed,
            },
        )
        try:
            media = self.repository.create(media)
            self.db.commit()
            return {"media": media, "ocr": ocr_result, "deduplicated": False}
        except SQLAlchemyError as exc:
            self.db.rollback()
            self._delete_stored_file(stored_file.file_path)
            raise MediaServiceError(f"Database write failed: {exc}") from exc

    def list_media(
        self,
        *,
        media_type: str | None = None,
        manufacturer: str | None = None,
        product_series: str | None = None,
        device_type: str | None = None,
        device_id: UUID | None = None,
        task_id: UUID | None = None,
        fault_type: str | None = None,
        alarm_code: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        self._validate_page(page, page_size)
        media_items, total = self.repository.list_media(
            media_type=media_type,
            manufacturer=manufacturer,
            product_series=product_series,
            device_type=device_type,
            device_id=device_id,
            task_id=task_id,
            fault_type=fault_type,
            alarm_code=alarm_code,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return {"items": media_items, "total": total, "page": page, "page_size": page_size}

    def get_media(self, media_id: UUID) -> UploadedMedia | None:
        return self.repository.get_by_id(media_id)

    def resolve_media_items(
        self,
        media_ids: list[UUID],
        *,
        device_id: UUID | None = None,
    ) -> list[UploadedMedia]:
        if len(media_ids) > 10:
            raise MediaServiceError("media_ids supports at most 10 media items")
        media_items = self.repository.get_by_ids(media_ids)
        found_ids = {item.id for item in media_items}
        missing = [str(media_id) for media_id in media_ids if media_id not in found_ids]
        if missing:
            raise MediaServiceError(f"Media not found: {', '.join(missing)}")
        for media in media_items:
            if media.status == "archived":
                raise MediaServiceError(f"Media is archived: {media.id}")
            if media.device_type != "pv_inverter":
                raise MediaServiceError(f"Media device_type must be pv_inverter: {media.id}")
            if device_id and media.device_id and media.device_id != device_id:
                raise MediaServiceError(f"Media does not belong to the selected device: {media.id}")
        return media_items

    def link_to_qa(self, media_items: list[UploadedMedia], trace_id: str) -> None:
        self.repository.link_to_qa(media_items, trace_id)

    def link_to_task(self, media_items: list[UploadedMedia], task_id: UUID) -> None:
        self.repository.link_to_task(media_items, task_id)

    def media_payload(self, media: UploadedMedia) -> dict:
        payload = {
            "id": str(media.id),
            "file_name": media.file_name,
            "original_file_name": media.original_file_name,
            "file_ext": media.file_ext,
            "mime_type": media.mime_type,
            "file_size": media.file_size,
            "media_type": media.media_type,
            "description": media.description,
            "ocr_text": media.ocr_text,
            "manufacturer": media.manufacturer,
            "product_series": media.product_series,
            "device_type": media.device_type,
            "device_id": str(media.device_id) if media.device_id else None,
            "task_id": str(media.task_id) if media.task_id else None,
            "diagnosis_record_id": str(media.diagnosis_record_id) if media.diagnosis_record_id else None,
            "qa_trace_id": media.qa_trace_id,
            "uploaded_by": str(media.uploaded_by) if media.uploaded_by else None,
            "status": media.status,
            "metadata_json": media.metadata_json or {},
            "fault_type": self._metadata_value(media, "fault_type"),
            "alarm_code": self._metadata_value(media, "alarm_code"),
            "ocr_status": self._metadata_value(media, "ocr_status") or "disabled",
            "ocr_message": self._metadata_value(media, "ocr_message") or "OCR service is not configured",
            "ocr_error_summary": self._metadata_value(media, "ocr_error_summary"),
            "ocr_provider": self._ocr_metadata_value(media, "provider") or self.settings.OCR_PROVIDER,
            "ocr_lang": self._ocr_metadata_value(media, "lang") or self.settings.OCR_LANG,
            "ocr_processed_at": self._metadata_value(media, "ocr_processed_at"),
            "preview_url": f"/api/media/{media.id}/content",
            "created_at": media.created_at.isoformat() if media.created_at else None,
            "updated_at": media.updated_at.isoformat() if media.updated_at else None,
        }
        uploader = self.repository.get_user(media.uploaded_by) if media.uploaded_by else None
        payload["uploaded_by_name"] = (uploader.display_name or uploader.username) if uploader else None
        device = self.repository.get_device(media.device_id) if media.device_id else None
        payload["device_name"] = device.device_name if device else None
        return payload

    def media_context(self, media: UploadedMedia) -> MediaContextItem:
        payload = self.media_payload(media)
        return MediaContextItem(
            id=media.id,
            file_name=media.file_name,
            original_file_name=media.original_file_name,
            media_type=media.media_type,
            description=media.description,
            manufacturer=media.manufacturer,
            product_series=media.product_series,
            device_type=media.device_type,
            device_id=media.device_id,
            device_name=payload.get("device_name"),
            task_id=media.task_id,
            fault_type=payload.get("fault_type"),
            alarm_code=payload.get("alarm_code"),
            ocr_status=payload.get("ocr_status") or "disabled",
            ocr_message=payload.get("ocr_message") or "OCR service is not configured",
            ocr_error_summary=payload.get("ocr_error_summary"),
            ocr_provider=payload.get("ocr_provider"),
            ocr_lang=payload.get("ocr_lang"),
            ocr_processed_at=payload.get("ocr_processed_at"),
            ocr_text=self._ocr_text_for_context(media),
            preview_url=payload["preview_url"],
            created_at=media.created_at,
        )

    def media_context_texts(
        self,
        media_items: list[UploadedMedia],
        *,
        include_ocr_text: bool = False,
    ) -> list[str]:
        texts: list[str] = []
        for media in media_items:
            values = [
                media.description,
                self._metadata_value(media, "fault_type"),
                self._metadata_value(media, "alarm_code"),
            ]
            if include_ocr_text and self._metadata_value(media, "ocr_status") == "processed" and media.ocr_text:
                values.append(media.ocr_text)
            for value in values:
                if value and value not in texts:
                    texts.append(str(value))
        return texts

    def ocr_context(self, media_items: list[UploadedMedia]) -> list[dict]:
        context: list[dict] = []
        for media in media_items:
            if self._metadata_value(media, "ocr_status") != "processed" or not media.ocr_text:
                continue
            text = self._ocr_text_for_context(media)
            context.append(
                {
                    "media_id": str(media.id),
                    "file_name": media.original_file_name or media.file_name,
                    "ocr_status": "processed",
                    "provider": self._ocr_metadata_value(media, "provider") or self.settings.OCR_PROVIDER,
                    "lang": self._ocr_metadata_value(media, "lang") or self.settings.OCR_LANG,
                    "text": text,
                    "notice": "OCR text is machine-recognized and for reference only.",
                    "processed_at": self._metadata_value(media, "ocr_processed_at"),
                }
            )
        return context

    def resolve_file_path(self, media: UploadedMedia) -> Path:
        stored_path = Path(media.file_path)
        path = (stored_path if stored_path.is_absolute() else self._backend_root() / stored_path).resolve()
        self._ensure_inside_upload_dir(path, self._safe_upload_dir())
        if not path.is_file():
            raise MediaServiceError("Media file is missing from storage")
        return path

    async def _store_upload(self, file: UploadFile) -> StoredMediaFile:
        original_name = Path(file.filename or "").name
        if not original_name:
            raise MediaServiceError("Uploaded file name is empty")
        safe_original_name = self._safe_name(original_name)
        file_ext = Path(safe_original_name).suffix.lower().lstrip(".")
        if file_ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise MediaServiceError("Unsupported image extension. Allowed: jpg, jpeg, png, webp")

        content = await file.read()
        if not content:
            raise MediaServiceError("Uploaded file is empty")
        max_bytes = self.settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(content) > max_bytes:
            raise MediaServiceError(f"Uploaded file exceeds {self.settings.MAX_UPLOAD_SIZE_MB}MB limit")

        source_sha256 = hashlib.sha256(content).hexdigest()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(content)) as probe:
                    detected_format = str(probe.format or "").upper()
                    width, height = probe.size
                    if detected_format not in IMAGE_FORMAT_RULES:
                        raise MediaServiceError("Unsupported image content. Allowed: JPEG, PNG, WEBP")
                    allowed_extensions, canonical_mime = IMAGE_FORMAT_RULES[detected_format]
                    if file_ext not in allowed_extensions:
                        raise MediaServiceError("Image extension does not match detected image format")
                    claimed_mime = (file.content_type or "").split(";", 1)[0].strip().lower()
                    if claimed_mime and claimed_mime != canonical_mime:
                        raise MediaServiceError("Image MIME type does not match detected image format")
                    if width < 1 or height < 1:
                        raise MediaServiceError("Uploaded image has invalid dimensions")
                    if width * height > self.settings.MULTIMODAL_MAX_IMAGE_PIXELS:
                        raise MediaServiceError(
                            f"Uploaded image exceeds {self.settings.MULTIMODAL_MAX_IMAGE_PIXELS} pixel limit"
                        )
                    probe.verify()

                with Image.open(io.BytesIO(content)) as opened:
                    original_orientation = self._read_orientation(opened)
                    opened.load()
                    normalized = ImageOps.exif_transpose(opened).copy()
                    sanitized = self._sanitized_image_bytes(normalized, detected_format)
        except MediaServiceError:
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise MediaServiceError("Uploaded image exceeds safe decompression limits") from exc
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
            raise MediaServiceError("Uploaded file is not a valid image") from exc

        upload_dir = self._safe_upload_dir()
        target_dir = upload_dir / datetime.now(timezone.utc).strftime("%Y%m%d")
        target_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid4().hex}.{file_ext}"
        target_path = (target_dir / stored_name).resolve()
        self._ensure_inside_upload_dir(target_path, upload_dir)
        target_path.write_bytes(sanitized)

        return StoredMediaFile(
            original_file_name=safe_original_name,
            file_name=stored_name,
            file_path=self._storage_path_value(target_path),
            file_ext=file_ext,
            file_size=len(sanitized),
            mime_type=canonical_mime,
            source_sha256=source_sha256,
            stored_sha256=hashlib.sha256(sanitized).hexdigest(),
            width=normalized.width,
            height=normalized.height,
            detected_format=detected_format,
            original_orientation=original_orientation,
            exif_removed=True,
        )

    @staticmethod
    def _read_orientation(image: Image.Image) -> int | None:
        try:
            value = image.getexif().get(274)
            return int(value) if value is not None else None
        except (AttributeError, TypeError, ValueError):
            return None

    @staticmethod
    def _sanitized_image_bytes(image: Image.Image, detected_format: str) -> bytes:
        output = io.BytesIO()
        if detected_format == "JPEG":
            clean = image.convert("RGB")
            clean.save(output, format="JPEG", quality=92, optimize=True)
        elif detected_format == "PNG":
            clean = image.convert("RGBA") if "A" in image.getbands() else image.convert("RGB")
            clean.save(output, format="PNG", optimize=True)
        else:
            clean = image.convert("RGBA") if "A" in image.getbands() else image.convert("RGB")
            clean.save(output, format="WEBP", quality=92, method=4)
        return output.getvalue()

    def _ocr_result_from_media(self, media: UploadedMedia) -> OCRRecognitionResult:
        metadata = media.metadata_json or {}
        ocr = metadata.get("ocr") if isinstance(metadata.get("ocr"), dict) else {}
        return OCRRecognitionResult(
            status=str(ocr.get("status") or metadata.get("ocr_status") or "disabled"),
            text=media.ocr_text or "",
            message=str(ocr.get("message") or metadata.get("ocr_message") or "OCR service is not configured"),
            error_summary=ocr.get("error_summary") or metadata.get("ocr_error_summary"),
            metadata=ocr.get("metadata") if isinstance(ocr.get("metadata"), dict) else {},
        )

    def _safe_upload_dir(self) -> Path:
        base = Path(self.settings.UPLOAD_DIR)
        if not base.is_absolute():
            base = self._backend_root() / base
        upload_dir = (base / "media").resolve()
        frontend_dir = (self._backend_root().parent / "frontend").resolve()
        try:
            upload_dir.relative_to(frontend_dir)
            raise MediaServiceError("Upload directory must not be under frontend")
        except ValueError:
            pass
        upload_dir.mkdir(parents=True, exist_ok=True)
        return upload_dir

    def _delete_stored_file(self, relative_path: str) -> None:
        try:
            stored_path = Path(relative_path)
            path = (stored_path if stored_path.is_absolute() else self._backend_root() / stored_path).resolve()
            self._ensure_inside_upload_dir(path, self._safe_upload_dir())
            if path.is_file():
                path.unlink()
        except (OSError, MediaServiceError):
            pass

    @staticmethod
    def _ensure_inside_upload_dir(path: Path, upload_dir: Path) -> None:
        try:
            path.relative_to(upload_dir.resolve())
        except ValueError as exc:
            raise MediaServiceError("Unsafe upload path") from exc

    @staticmethod
    def _safe_name(file_name: str) -> str:
        name = Path(file_name).name.strip()
        name = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "_", name)
        if name in {"", ".", ".."}:
            raise MediaServiceError("Uploaded file name is invalid")
        return name[:180]

    @staticmethod
    def _validate_media_type(media_type: str) -> None:
        if media_type not in ALLOWED_MEDIA_TYPES:
            raise MediaServiceError("Invalid media_type")

    @staticmethod
    def _validate_domain(
        manufacturer: str | None,
        product_series: str | None,
        device_type: str,
    ) -> None:
        if manufacturer and manufacturer not in ALLOWED_MANUFACTURERS:
            raise MediaServiceError("Invalid manufacturer")
        if product_series and product_series not in ALLOWED_PRODUCT_SERIES:
            raise MediaServiceError("Invalid product_series")
        if device_type not in ALLOWED_DEVICE_TYPES:
            raise MediaServiceError("Invalid device_type")

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise MediaServiceError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise MediaServiceError("page_size must be between 1 and 100")

    @staticmethod
    def _clean_metadata_text(value: str | None, max_length: int) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned[:max_length] or None

    @staticmethod
    def _metadata_value(media: UploadedMedia, key: str) -> str | None:
        value = (media.metadata_json or {}).get(key)
        return str(value) if value not in {None, ""} else None

    @staticmethod
    def _ocr_metadata_value(media: UploadedMedia, key: str) -> str | None:
        ocr = (media.metadata_json or {}).get("ocr")
        if not isinstance(ocr, dict):
            return None
        value = ocr.get(key)
        return str(value) if value not in {None, ""} else None

    @staticmethod
    def _ocr_text_for_context(media: UploadedMedia) -> str | None:
        if not media.ocr_text:
            return None
        compact = re.sub(r"\s+", " ", media.ocr_text).strip()
        return compact[:1000] if compact else None

    @staticmethod
    def _backend_root() -> Path:
        return Path(__file__).resolve().parents[2]

    def _storage_path_value(self, path: Path) -> str:
        try:
            return path.relative_to(self._backend_root()).as_posix()
        except ValueError:
            return path.as_posix()
