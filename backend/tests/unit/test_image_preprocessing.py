from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PIL import Image

from app.services.image_preprocessing_service import ImagePreprocessingService


def test_preprocessing_creates_exif_free_deterministic_variants(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    Image.new("RGB", (1600, 900), color=(90, 130, 170)).save(source, format="JPEG")

    result = ImagePreprocessingService(output_root=tmp_path / "derived").process(
        media_id=uuid4(),
        source_path=source,
    )

    assert result.original_width == 1600
    assert result.original_height == 900
    assert result.orientation == "landscape"
    assert result.exif_removed is True
    assert {item.variant_id for item in result.variants} == {
        "normalized",
        "ocr_r0",
        "ocr_r90",
        "ocr_r180",
        "ocr_r270",
        "center_region",
    }
    assert all(len(item.sha256) == 64 for item in result.variants)
    assert all(".." not in item.relative_path for item in result.variants)


def test_preprocessing_flags_unusable_dark_small_image(tmp_path: Path) -> None:
    source = tmp_path / "dark.png"
    Image.new("RGB", (120, 100), color=(0, 0, 0)).save(source, format="PNG")

    result = ImagePreprocessingService(output_root=tmp_path / "derived").process(
        media_id=uuid4(),
        source_path=source,
    )

    assert "too_small" in result.quality_flags
    assert "severely_dark" in result.quality_flags
    assert result.ocr_ready is False
    assert result.vision_ready is False
