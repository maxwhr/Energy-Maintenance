from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from app.services.ocr_adapters.base import OCRAvailability, OCRRecognitionResult


ALLOWED_OCR_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


class TesseractOCRAdapter:
    def __init__(self, command: str = "tesseract", lang: str = "chi_sim+eng"):
        self.command = command.strip() or "tesseract"
        self.lang = lang.strip() or "chi_sim+eng"

    def check_availability(self) -> OCRAvailability:
        executable = self._resolve_command()
        if not executable:
            return OCRAvailability(
                status="not_configured",
                available=False,
                message="Tesseract command was not found",
                error_summary=f"Command not found: {self._command_label()}",
                metadata={"provider": "tesseract", "command": self._command_label()},
            )

        version = self._run([executable, "--version"], timeout=8)
        if version.returncode != 0:
            return OCRAvailability(
                status="not_configured",
                available=False,
                message="Tesseract command is not usable",
                error_summary=self._sanitize(version.stderr or version.stdout),
                metadata={"provider": "tesseract", "command": self._command_label()},
            )

        languages = self._run([executable, "--list-langs"], timeout=8)
        missing = self._missing_languages(languages.stdout if languages.returncode == 0 else "")
        if missing:
            return OCRAvailability(
                status="not_configured",
                available=False,
                message="Tesseract language package is missing",
                error_summary=f"Missing language packages: {', '.join(missing)}",
                metadata={
                    "provider": "tesseract",
                    "command": self._command_label(),
                    "required_lang": self.lang,
                },
            )

        return OCRAvailability(
            status="available",
            available=True,
            message="Tesseract OCR is available",
            metadata={
                "provider": "tesseract",
                "command": self._command_label(),
                "lang": self.lang,
                "version": self._first_line(version.stdout),
            },
        )

    def recognize_image(self, image_path: str, lang: str, timeout: int) -> OCRRecognitionResult:
        path = Path(image_path)
        file_ext = path.suffix.lower().lstrip(".")
        if file_ext not in ALLOWED_OCR_IMAGE_EXTENSIONS:
            return OCRRecognitionResult(
                status="failed",
                message="Unsupported image type for OCR",
                error_summary="Only jpg, jpeg, png, and webp are supported",
                metadata={"provider": "tesseract", "file_ext": file_ext},
            )

        executable = self._resolve_command()
        if not executable:
            return OCRRecognitionResult(
                status="not_configured",
                message="Tesseract command was not found",
                error_summary=f"Command not found: {self._command_label()}",
                metadata={"provider": "tesseract"},
            )

        result = self._run([executable, str(path), "stdout", "-l", lang], timeout=timeout)
        if result.timed_out:
            return OCRRecognitionResult(
                status="failed",
                message="OCR recognition timed out",
                error_summary=f"Tesseract exceeded {timeout} seconds",
                metadata={"provider": "tesseract", "lang": lang},
            )
        if result.returncode != 0:
            return OCRRecognitionResult(
                status="failed",
                message="OCR recognition failed",
                error_summary=self._sanitize(result.stderr or result.stdout),
                metadata={"provider": "tesseract", "lang": lang},
            )

        text = self._clean_text(result.stdout)
        if not text:
            return OCRRecognitionResult(
                status="failed",
                message="OCR completed but no text was recognized",
                error_summary="No text recognized from image",
                metadata={"provider": "tesseract", "lang": lang},
            )

        return OCRRecognitionResult(
            status="processed",
            text=text,
            message="OCR text recognized",
            metadata={"provider": "tesseract", "lang": lang, "char_count": len(text)},
        )

    def _resolve_command(self) -> str | None:
        command_path = Path(self.command)
        if command_path.is_absolute() and command_path.exists():
            return str(command_path)
        return shutil.which(self.command)

    def _missing_languages(self, output: str) -> list[str]:
        available = {line.strip() for line in output.splitlines() if line.strip() and not line.startswith("List of")}
        required = [item.strip() for item in re.split(r"[+,]", self.lang) if item.strip()]
        return [item for item in required if item not in available]

    @staticmethod
    def _run(command: list[str], timeout: int):
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
            return _CommandResult(completed.returncode, completed.stdout, completed.stderr, False)
        except subprocess.TimeoutExpired as exc:
            return _CommandResult(124, exc.stdout or "", exc.stderr or "", True)
        except OSError as exc:
            return _CommandResult(127, "", str(exc), False)

    @staticmethod
    def _clean_text(value: str) -> str:
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.replace("\r\n", "\n").split("\n")]
        return "\n".join(line for line in lines if line).strip()

    @staticmethod
    def _first_line(value: str) -> str | None:
        for line in value.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:160]
        return None

    def _command_label(self) -> str:
        return Path(self.command).name or "tesseract"

    @staticmethod
    def _sanitize(value: str | None) -> str:
        if not value:
            return "No error details were returned"
        sanitized = re.sub(r"[A-Za-z]:\\[^\s]+", "<local-path>", value)
        sanitized = re.sub(r"/[^\s]+", "<local-path>", sanitized)
        return sanitized.strip()[:500]


class _CommandResult:
    def __init__(self, returncode: int, stdout: str | bytes | None, stderr: str | bytes | None, timed_out: bool):
        self.returncode = returncode
        self.stdout = self._to_text(stdout)
        self.stderr = self._to_text(stderr)
        self.timed_out = timed_out

    @staticmethod
    def _to_text(value: str | bytes | None) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value
