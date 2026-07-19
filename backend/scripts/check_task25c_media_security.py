from __future__ import annotations

import asyncio
import io
import tempfile
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, ImageDraw
from uuid import uuid4

from app.core.database import SessionLocal
from app.services.image_preprocessing_service import ImagePreprocessingService
from app.services.media_service import MediaService, MediaServiceError
from task25c_common import now_iso, write_json


async def inspect_upload(service: MediaService, name: str, mime: str, content: bytes) -> dict:
    upload = UploadFile(filename=name, file=io.BytesIO(content), headers={"content-type": mime})
    try:
        stored = await service._store_upload(upload)
    except MediaServiceError as exc:
        return {"accepted": False, "reason": str(exc)}
    path = service._backend_root() / stored.file_path
    if Path(stored.file_path).is_absolute():
        path = Path(stored.file_path)
    try:
        return {
            "accepted": True,
            "detected_format": stored.detected_format,
            "mime_type": stored.mime_type,
            "source_hash_present": len(stored.source_sha256) == 64,
            "stored_hash_present": len(stored.stored_sha256) == 64,
            "random_safe_name": Path(stored.file_name).stem.isalnum() and ".." not in stored.file_name,
            "exif_removed": stored.exif_removed,
        }
    finally:
        path.unlink(missing_ok=True)


async def run() -> dict:
    image_buffer = io.BytesIO()
    image = Image.new("RGB", (1280, 720), "white")
    drawing = ImageDraw.Draw(image)
    drawing.rectangle((40, 40, 1240, 680), outline="black", width=12)
    drawing.rectangle((180, 180, 1100, 540), fill="navy")
    for offset in range(220, 1060, 100):
        drawing.line((offset, 200, offset, 520), fill="white", width=8)
    image.save(image_buffer, format="PNG")
    valid = image_buffer.getvalue()
    with SessionLocal() as db:
        service = MediaService(db)
        checks = {
            "valid_png": await inspect_upload(service, "nameplate.png", "image/png", valid),
            "mime_mismatch": await inspect_upload(service, "nameplate.png", "image/jpeg", valid),
            "extension_mismatch": await inspect_upload(service, "nameplate.jpg", "image/jpeg", valid),
            "invalid_bytes": await inspect_upload(service, "nameplate.png", "image/png", b"not-an-image"),
            "path_traversal_name": await inspect_upload(service, "../../nameplate.png", "image/png", valid),
        }
    with tempfile.TemporaryDirectory(prefix="task25c-preprocess-") as temp_dir:
        source = Path(temp_dir) / "source.png"
        source.write_bytes(valid)
        result = ImagePreprocessingService(output_root=Path(temp_dir) / "derived").process(
            media_id=uuid4(), source_path=source
        )
        preprocessing = {
            "source_unchanged": source.read_bytes() == valid,
            "variants": len(result.variants),
            "hashes_valid": len(result.source_sha256) == 64 and all(len(item.sha256) == 64 for item in result.variants),
            "ocr_ready": result.ocr_ready,
            "vision_ready": result.vision_ready,
        }
    passed = (
        checks["valid_png"].get("accepted") is True
        and checks["mime_mismatch"].get("accepted") is False
        and checks["extension_mismatch"].get("accepted") is False
        and checks["invalid_bytes"].get("accepted") is False
        and checks["path_traversal_name"].get("accepted") is True
        and all(bool(value) for value in preprocessing.values())
    )
    return {"generated_at": now_iso(), "status": "PASS" if passed else "FAIL", "checks": checks, "preprocessing": preprocessing}


def main() -> int:
    payload = asyncio.run(run())
    write_json("media_security.json", payload)
    print(payload["status"])
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
