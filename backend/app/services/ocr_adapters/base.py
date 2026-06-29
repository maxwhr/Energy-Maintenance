from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(slots=True)
class OCRAvailability:
    status: str
    available: bool
    message: str
    error_summary: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class OCRRecognitionResult:
    status: str
    text: str = ""
    message: str = ""
    error_summary: str | None = None
    metadata: dict = field(default_factory=dict)


class OCRAdapter(Protocol):
    def check_availability(self) -> OCRAvailability:
        ...

    def recognize_image(self, image_path: str, lang: str, timeout: int) -> OCRRecognitionResult:
        ...
