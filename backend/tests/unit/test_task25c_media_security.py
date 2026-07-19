from __future__ import annotations

import hashlib
import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import UploadFile
from PIL import Image

from app.services.media_service import MediaService, MediaServiceError


def _image_bytes(image_format: str, size: tuple[int, int] = (320, 240)) -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", size, color=(40, 90, 130)).save(stream, format=image_format)
    return stream.getvalue()


def _service(tmp_path: Path, *, pixel_limit: int = 1_000_000) -> MediaService:
    service = object.__new__(MediaService)
    service.settings = SimpleNamespace(
        UPLOAD_DIR=str(tmp_path / "uploads"),
        MAX_UPLOAD_SIZE_MB=5,
        MULTIMODAL_MAX_IMAGE_PIXELS=pixel_limit,
    )
    return service


@pytest.mark.asyncio
async def test_store_upload_validates_and_sanitizes_image(tmp_path: Path) -> None:
    content = _image_bytes("JPEG")
    upload = UploadFile(filename="fault.jpg", file=io.BytesIO(content), headers={"content-type": "image/jpeg"})

    stored = await _service(tmp_path)._store_upload(upload)

    assert stored.mime_type == "image/jpeg"
    assert stored.width == 320
    assert stored.height == 240
    assert stored.source_sha256 == hashlib.sha256(content).hexdigest()
    assert len(stored.stored_sha256) == 64
    assert stored.exif_removed is True
    stored_path = Path(stored.file_path)
    assert stored_path.is_file()


@pytest.mark.asyncio
async def test_store_upload_rejects_spoofed_extension(tmp_path: Path) -> None:
    upload = UploadFile(
        filename="spoof.jpg",
        file=io.BytesIO(_image_bytes("PNG")),
        headers={"content-type": "image/jpeg"},
    )

    with pytest.raises(MediaServiceError, match="extension does not match"):
        await _service(tmp_path)._store_upload(upload)


@pytest.mark.asyncio
async def test_store_upload_rejects_pixel_limit(tmp_path: Path) -> None:
    upload = UploadFile(
        filename="large.png",
        file=io.BytesIO(_image_bytes("PNG", (1200, 1200))),
        headers={"content-type": "image/png"},
    )

    with pytest.raises(MediaServiceError, match="pixel limit"):
        await _service(tmp_path, pixel_limit=1_000_000)._store_upload(upload)
