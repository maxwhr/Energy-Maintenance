from __future__ import annotations

import hashlib
import warnings
from dataclasses import asdict, dataclass, field
from pathlib import Path
from uuid import UUID

from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError

from app.core.config import get_settings


class ImagePreprocessingError(ValueError):
    pass


@dataclass(slots=True)
class ImageVariant:
    variant_id: str
    purpose: str
    relative_path: str
    sha256: str
    width: int
    height: int
    rotation_degrees: int = 0
    bbox: list[float] | None = None
    transform: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ImagePreprocessingResult:
    media_id: str
    source_sha256: str
    original_width: int
    original_height: int
    normalized_width: int
    normalized_height: int
    orientation: str
    brightness_mean: float
    contrast_stddev: float
    edge_variance: float
    dark_pixel_ratio: float
    bright_pixel_ratio: float
    quality_flags: list[str]
    ocr_ready: bool
    vision_ready: bool
    exif_removed: bool
    variants: list[ImageVariant]

    def as_dict(self) -> dict:
        return asdict(self)


class ImagePreprocessingService:
    """Create deterministic, EXIF-free derivatives without altering source media."""

    def __init__(self, output_root: Path | None = None):
        self.settings = get_settings()
        self.backend_root = Path(__file__).resolve().parents[2]
        self.output_root = (output_root or self.backend_root / "storage" / "uploads" / "media-derived").resolve()

    def process(
        self,
        *,
        media_id: UUID | str,
        source_path: Path | str,
        source_sha256: str | None = None,
    ) -> ImagePreprocessingResult:
        safe_media_id = str(UUID(str(media_id)))
        source = Path(source_path).resolve()
        if not source.is_file():
            raise ImagePreprocessingError("Source image is missing")

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(source) as opened:
                    width, height = opened.size
                    if width < 1 or height < 1:
                        raise ImagePreprocessingError("Source image has invalid dimensions")
                    if width * height > self.settings.MULTIMODAL_MAX_IMAGE_PIXELS:
                        raise ImagePreprocessingError("Source image exceeds safe pixel limit")
                    opened.load()
                    normalized = ImageOps.exif_transpose(opened).convert("RGB")
        except ImagePreprocessingError:
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise ImagePreprocessingError("Source image exceeds safe decompression limits") from exc
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ImagePreprocessingError("Source file is not a valid image") from exc

        original_width, original_height = width, height
        normalized.thumbnail(
            (self.settings.MULTIMODAL_PREPROCESS_MAX_EDGE, self.settings.MULTIMODAL_PREPROCESS_MAX_EDGE),
            Image.Resampling.LANCZOS,
        )
        gray = ImageOps.grayscale(normalized)
        stats = ImageStat.Stat(gray)
        brightness = float(stats.mean[0])
        contrast = float(stats.stddev[0])
        edge_variance = float(ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).var[0])
        histogram = gray.histogram()
        pixels = max(1, normalized.width * normalized.height)
        dark_ratio = sum(histogram[:26]) / pixels
        bright_ratio = sum(histogram[245:]) / pixels
        quality_flags = self._quality_flags(
            width=normalized.width,
            height=normalized.height,
            brightness=brightness,
            contrast=contrast,
            edge_variance=edge_variance,
            dark_ratio=dark_ratio,
            bright_ratio=bright_ratio,
        )

        derived_dir = (self.output_root / safe_media_id).resolve()
        self._ensure_inside(derived_dir, self.output_root)
        derived_dir.mkdir(parents=True, exist_ok=True)
        variants: list[ImageVariant] = []
        variants.append(self._save_variant(derived_dir, "normalized", "vision", normalized, ["exif_transpose", "resize"]))

        enhanced = ImageEnhance.Sharpness(ImageOps.autocontrast(gray)).enhance(1.5)
        for degrees in (0, 90, 180, 270):
            rotated = enhanced.rotate(degrees, expand=True) if degrees else enhanced
            variants.append(
                self._save_variant(
                    derived_dir,
                    f"ocr_r{degrees}",
                    "ocr",
                    rotated,
                    ["grayscale", "autocontrast", "sharpen", f"rotate_{degrees}"],
                    rotation_degrees=degrees,
                )
            )

        bbox = self._center_region_bbox(normalized.width, normalized.height)
        left = int(bbox[0] * normalized.width)
        top = int(bbox[1] * normalized.height)
        right = max(left + 1, int(bbox[2] * normalized.width))
        bottom = max(top + 1, int(bbox[3] * normalized.height))
        region = normalized.crop((left, top, right, bottom))
        variants.append(
            self._save_variant(
                derived_dir,
                "center_region",
                "region_candidate",
                region,
                ["center_region_crop"],
                bbox=bbox,
            )
        )

        computed_source_hash = source_sha256 or self._sha256_file(source)
        severe_flags = {"too_small", "severely_dark", "severely_overexposed"}
        ocr_ready = not bool(severe_flags.intersection(quality_flags)) and "very_low_contrast" not in quality_flags
        vision_ready = not bool(severe_flags.intersection(quality_flags))
        return ImagePreprocessingResult(
            media_id=safe_media_id,
            source_sha256=computed_source_hash,
            original_width=original_width,
            original_height=original_height,
            normalized_width=normalized.width,
            normalized_height=normalized.height,
            orientation=self._orientation(normalized.width, normalized.height),
            brightness_mean=round(brightness, 3),
            contrast_stddev=round(contrast, 3),
            edge_variance=round(edge_variance, 3),
            dark_pixel_ratio=round(dark_ratio, 6),
            bright_pixel_ratio=round(bright_ratio, 6),
            quality_flags=quality_flags,
            ocr_ready=ocr_ready,
            vision_ready=vision_ready,
            exif_removed=True,
            variants=variants,
        )

    def _save_variant(
        self,
        directory: Path,
        variant_id: str,
        purpose: str,
        image: Image.Image,
        transform: list[str],
        *,
        rotation_degrees: int = 0,
        bbox: list[float] | None = None,
    ) -> ImageVariant:
        path = (directory / f"{variant_id}.png").resolve()
        self._ensure_inside(path, directory)
        clean = image.convert("L") if image.mode == "L" else image.convert("RGB")
        clean.save(path, format="PNG", optimize=True)
        return ImageVariant(
            variant_id=variant_id,
            purpose=purpose,
            relative_path=self._relative_path(path),
            sha256=self._sha256_file(path),
            width=clean.width,
            height=clean.height,
            rotation_degrees=rotation_degrees,
            bbox=bbox,
            transform=transform,
        )

    @staticmethod
    def _quality_flags(
        *,
        width: int,
        height: int,
        brightness: float,
        contrast: float,
        edge_variance: float,
        dark_ratio: float,
        bright_ratio: float,
    ) -> list[str]:
        flags: list[str] = []
        if min(width, height) < 240:
            flags.append("too_small")
        if brightness < 45 or dark_ratio > 0.70:
            flags.append("severely_dark")
        elif brightness < 75:
            flags.append("dark")
        if brightness > 235 or bright_ratio > 0.70:
            flags.append("severely_overexposed")
        elif brightness > 205:
            flags.append("overexposed")
        if contrast < 12:
            flags.append("very_low_contrast")
        elif contrast < 25:
            flags.append("low_contrast")
        if edge_variance < 20:
            flags.append("possibly_blurry")
        return flags

    @staticmethod
    def _center_region_bbox(width: int, height: int) -> list[float]:
        if width >= height:
            return [0.10, 0.15, 0.90, 0.85]
        return [0.08, 0.18, 0.92, 0.82]

    @staticmethod
    def _orientation(width: int, height: int) -> str:
        if width == height:
            return "square"
        return "landscape" if width > height else "portrait"

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def _relative_path(self, path: Path) -> str:
        try:
            return path.relative_to(self.backend_root).as_posix()
        except ValueError:
            return path.name

    @staticmethod
    def _ensure_inside(path: Path, root: Path) -> None:
        try:
            path.relative_to(root.resolve())
        except ValueError as exc:
            raise ImagePreprocessingError("Unsafe derived image path") from exc
