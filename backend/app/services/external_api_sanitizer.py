from __future__ import annotations

import re
from typing import Any


class ExternalApiSanitizer:
    """Central sanitizer for provider payloads and logs.

    It intentionally keeps only operational summaries for media input and
    strips secrets, local paths, authorization headers, and base64 payloads.
    """

    SECRET_KEY_PATTERN = re.compile(r"(api[_-]?key|authorization|token|secret|password)", re.IGNORECASE)
    PATH_KEY_PATTERN = re.compile(r"(^|_)(file|local)?path$", re.IGNORECASE)
    BINARY_KEY_PATTERN = re.compile(r"(base64|image_data|binary|bytes|blob)", re.IGNORECASE)
    BASE64_TEXT_PATTERN = re.compile(r"^[A-Za-z0-9+/=\s]{80,}$")
    DATA_IMAGE_TEXT_PATTERN = re.compile(r"data:image/[A-Za-z0-9.+-]+;base64,[A-Za-z0-9+/=\s]+", re.IGNORECASE)
    BEARER_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)
    SECRET_ASSIGNMENT_PATTERN = re.compile(
        r"\b([A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD|PRIVATE_KEY)[A-Z0-9_]*)\s*[:=]\s*([^\s,;\"']+)",
        re.IGNORECASE,
    )
    SK_PATTERN = re.compile(r"\b(sk-[A-Za-z0-9][A-Za-z0-9._-]{8,})")
    WINDOWS_PATH_PATTERN = re.compile(r"\b[A-Za-z]:\\(?:[^\\/:*?\"<>|\r\n]+\\)*[^\\/:*?\"<>|\r\n]*")
    UNIX_PATH_PATTERN = re.compile(r"(?<!\w)/(?:home|Users|mnt|var|tmp|data|opt)/[^\s,;\"']+")

    @classmethod
    def sanitize(cls, value: Any, *, max_list_items: int = 20, max_text_length: int = 240) -> Any:
        if isinstance(value, dict):
            return cls._sanitize_dict(value, max_list_items=max_list_items, max_text_length=max_text_length)
        if isinstance(value, list):
            return [
                cls.sanitize(item, max_list_items=max_list_items, max_text_length=max_text_length)
                for item in value[:max_list_items]
            ]
        if isinstance(value, tuple):
            return [
                cls.sanitize(item, max_list_items=max_list_items, max_text_length=max_text_length)
                for item in value[:max_list_items]
            ]
        if isinstance(value, str):
            return cls._sanitize_text(value, max_text_length=max_text_length)
        return value

    @classmethod
    def _sanitize_dict(cls, value: dict[str, Any], *, max_list_items: int, max_text_length: int) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key)
            if cls.SECRET_KEY_PATTERN.search(normalized_key):
                # Do not persist or expose secret/header field names such as
                # Authorization. Keeping the key itself can still reveal that
                # a credential-bearing header was present.
                continue
            if cls.PATH_KEY_PATTERN.search(normalized_key) or cls.BINARY_KEY_PATTERN.search(normalized_key):
                result[normalized_key] = "***omitted***"
                continue
            if normalized_key == "image_url" and isinstance(item, dict):
                result[normalized_key] = cls._sanitize_image_url(item)
                continue
            result[normalized_key] = cls.sanitize(
                item,
                max_list_items=max_list_items,
                max_text_length=max_text_length,
            )
        return result

    @classmethod
    def _sanitize_image_url(cls, value: dict[str, Any]) -> dict[str, Any]:
        sanitized = cls.sanitize(value)
        url = sanitized.get("url")
        if isinstance(url, str) and (url.startswith("data:image/") or url == "***omitted***"):
            sanitized["url"] = "<redacted_base64_image>"
            sanitized["image_count"] = 1
        return sanitized

    @classmethod
    def _sanitize_text(cls, value: str, *, max_text_length: int) -> str:
        stripped = value.strip()
        if stripped.startswith("data:image/"):
            return "<redacted_base64_image>"
        if cls.BASE64_TEXT_PATTERN.fullmatch(stripped) and len(stripped) > 80:
            return "***omitted***"
        stripped = cls.DATA_IMAGE_TEXT_PATTERN.sub("<redacted_base64_image>", stripped)
        stripped = cls.BEARER_PATTERN.sub("Bearer ***redacted***", stripped)
        stripped = cls.SECRET_ASSIGNMENT_PATTERN.sub(lambda match: f"{match.group(1)}=***redacted***", stripped)
        stripped = cls.SK_PATTERN.sub(lambda match: cls._mask_secret(match.group(1)), stripped)
        stripped = cls.WINDOWS_PATH_PATTERN.sub("<redacted_local_path>", stripped)
        stripped = cls.UNIX_PATH_PATTERN.sub("<redacted_local_path>", stripped)
        if len(stripped) > max_text_length:
            return f"{stripped[:max_text_length]}..."
        return stripped

    @staticmethod
    def _mask_secret(value: str) -> str:
        if len(value) <= 8:
            return "***redacted***"
        return f"{value[:3]}****{value[-4:]}"
