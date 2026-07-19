from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import UploadFile

from app.services.knowledge_service import KnowledgeService


def _service(upload_dir: Path) -> KnowledgeService:
    service = object.__new__(KnowledgeService)
    service.settings = SimpleNamespace(
        UPLOAD_DIR=str(upload_dir),
        MAX_UPLOAD_SIZE_MB=5,
        allowed_document_extensions={"txt"},
    )
    return service


@pytest.mark.asyncio
async def test_store_upload_supports_absolute_root_outside_backend(tmp_path: Path) -> None:
    upload_root = (tmp_path / "external-uploads").resolve()
    upload = UploadFile(filename="maintenance.txt", file=io.BytesIO(b"SUN2000 maintenance evidence"))

    stored = await _service(upload_root)._store_upload(upload, "documents")

    stored_path = Path(stored.file_path)
    assert stored_path.is_absolute()
    assert stored_path.is_file()
    stored_path.resolve().relative_to((upload_root / "documents").resolve())
