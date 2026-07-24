from __future__ import annotations

from pydantic import Field


class MultimodalSettings:
    OCR_ENABLED: bool = False
    OCR_PROVIDER: str = "tesseract"
    OCR_LANG: str = "chi_sim+eng"
    OCR_TIMEOUT_SECONDS: int = 30
    OCR_MAX_IMAGE_MB: int = 10
    OCR_TESSERACT_CMD: str = "tesseract"

    TASK25C_ALLOW_REAL_API: bool = False
    MULTIMODAL_MAX_IMAGE_PIXELS: int = Field(
        default=40_000_000,
        ge=1_000_000,
        le=100_000_000,
    )
    MULTIMODAL_PREPROCESS_MAX_EDGE: int = Field(
        default=2400,
        ge=640,
        le=8192,
    )
    MULTIMODAL_MAX_MEDIA_PER_CASE: int = Field(default=10, ge=1, le=20)
    MULTIMODAL_OCR_MIN_CONFIDENCE: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
    )
    MULTIMODAL_VISION_MIN_CONFIDENCE: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
    )
    MULTIMODAL_CONFIRMED_MIN_CONFIDENCE: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
    )
