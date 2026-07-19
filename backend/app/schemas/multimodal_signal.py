from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class VisualRegion(BaseModel):
    region_id: str = Field(min_length=1, max_length=128)
    bounding_box: list[float] = Field(min_length=4, max_length=4)
    region_type: Literal["NAMEPLATE", "SCREEN", "INDICATOR_LIGHT", "COMPONENT", "PHYSICAL_DAMAGE", "GENERAL"]
    text: str | None = Field(default=None, max_length=1000)
    attributes: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=0.99)

    @field_validator("bounding_box")
    @classmethod
    def validate_bbox(cls, value: list[float]) -> list[float]:
        if any(item < 0.0 or item > 1.0 for item in value):
            raise ValueError("bounding_box coordinates must be normalized to 0..1")
        if value[2] <= value[0] or value[3] <= value[1]:
            raise ValueError("bounding_box must have positive area")
        return value


class VisualSignalResult(BaseModel):
    observations: list[str] = Field(default_factory=list, max_length=50)
    regions: list[VisualRegion] = Field(default_factory=list, max_length=100)
    candidate_device_type: str | None = Field(default=None, max_length=64)
    candidate_components: list[str] = Field(default_factory=list, max_length=30)
    indicator_states: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    visible_damage: list[str] = Field(default_factory=list, max_length=30)
    screen_present: bool = False
    nameplate_present: bool = False
    needs_ocr: bool = False
    image_quality_issue: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(default=0.0, ge=0.0, le=0.99)
    provider: str | None = None
    provider_model: str | None = None
    provider_trace_id: str | None = None
    unsupported_fields_removed: list[str] = Field(default_factory=list)
