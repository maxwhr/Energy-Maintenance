from __future__ import annotations


class StorageSettings:
    UPLOAD_DIR: str = "storage/uploads"
    MEDIA_PROCESSED_DIR: str = "storage/processed-media"
    TEMP_DIR: str = ".runtime/tmp"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_DOCUMENT_EXTENSIONS: str = "txt,md,pdf,docx"
    LOG_DIR: str = ".runtime/logs"
