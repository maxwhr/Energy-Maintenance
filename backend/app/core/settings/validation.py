from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import model_validator


PLACEHOLDER_VALUES = {
    "",
    "change-this-secret-in-production",
    "energy-maintenance-local-dev-secret-change-me",
    "changeme",
    "change_me",
    "password",
    "admin",
    "123456",
}

WEAK_ADMIN_PASSWORDS = {
    "",
    "admin",
    "password",
    "123456",
    "admin123",
    "admin123456",
    "changeme",
    "change_me",
}

PROVIDER_REQUIREMENTS = (
    (
        "DASHVECTOR_ENABLED",
        "DASHVECTOR_API_KEY",
        "DASHVECTOR_ENDPOINT",
        "DASHVECTOR_COLLECTION",
        "DashVector",
    ),
    (
        "DASHSCOPE_RERANK_ENABLED",
        "DASHSCOPE_API_KEY",
        "DASHSCOPE_RERANK_BASE_URL",
        "DASHSCOPE_RERANK_MODEL",
        "DashScope Qwen3 Rerank",
    ),
    (
        "EMBEDDING_ENABLED",
        "EMBEDDING_API_KEY",
        "EMBEDDING_BASE_URL",
        "EMBEDDING_MODEL",
        "Embedding",
    ),
    (
        "CLOUD_LLM_ENABLED",
        "CLOUD_LLM_API_KEY",
        "CLOUD_LLM_BASE_URL",
        "CLOUD_LLM_MODEL",
        "Cloud LLM",
    ),
    (
        "MIMO_ENABLED",
        "MIMO_API_KEY",
        "MIMO_BASE_URL",
        "MIMO_MODEL",
        "MIMO",
    ),
    (
        "OCR_API_ENABLED",
        "OCR_API_KEY",
        "OCR_API_BASE_URL",
        "OCR_API_MODEL",
        "OCR API",
    ),
)


class SettingsValidation:
    @property
    def database_url(self) -> str:
        return self.DATABASE_URL

    @property
    def allowed_document_extensions(self) -> list[str]:
        return self._csv_values(self.ALLOWED_DOCUMENT_EXTENSIONS, lower=True)

    @property
    def cors_allowed_origins(self) -> list[str]:
        return self._csv_values(self.CORS_ALLOWED_ORIGINS)

    @property
    def cors_allow_methods(self) -> list[str]:
        return self._csv_values(self.CORS_ALLOW_METHODS)

    @property
    def cors_allow_headers(self) -> list[str]:
        return self._csv_values(self.CORS_ALLOW_HEADERS)

    @property
    def rate_limit_exempt_paths(self) -> list[str]:
        return self._csv_values(self.RATE_LIMIT_EXEMPT_PATHS)

    @property
    def security_scan_exclude_dirs(self) -> list[str]:
        return self._csv_values(self.SECURITY_SCAN_EXCLUDE_DIRS)

    @property
    def EXTERNAL_MODEL_CALLS_ALLOWED(self) -> bool:
        """Product-semantic alias; the legacy TASK25B flag remains authoritative."""
        return bool(self.TASK25B_ALLOW_REAL_API)

    @property
    def MULTIMODAL_EXTERNAL_CALLS_ALLOWED(self) -> bool:
        """Product-semantic alias; the legacy TASK25C flag remains authoritative."""
        return bool(self.TASK25C_ALLOW_REAL_API)

    @staticmethod
    def _csv_values(value: str, *, lower: bool = False) -> list[str]:
        items = [item.strip() for item in value.split(",") if item.strip()]
        return [item.lower() for item in items] if lower else items

    @model_validator(mode="after")
    def validate_production_secret(self) -> "SettingsValidation":
        if (
            self.APP_ENV.strip().lower() == "production"
            and self.SECRET_KEY == "change-this-secret-in-production"
        ):
            raise ValueError("SECRET_KEY must be replaced before production startup")
        return self


def is_configured_secret(value: str | None) -> bool:
    if value is None:
        return False
    stripped = str(value).strip()
    if not stripped:
        return False
    if stripped.startswith("<FILL_") and stripped.endswith(">"):
        return False
    if stripped.lower() in PLACEHOLDER_VALUES:
        return False
    return True


def provider_configuration_errors(settings: Any) -> list[str]:
    errors: list[str] = []
    for enabled_attr, key_attr, url_attr, model_attr, name in PROVIDER_REQUIREMENTS:
        if not bool(getattr(settings, enabled_attr)):
            continue
        missing = [
            attr
            for attr in (key_attr, url_attr, model_attr)
            if not is_configured_secret(str(getattr(settings, attr, "")))
        ]
        if missing:
            errors.append(
                f"{name} is enabled but not fully configured: {', '.join(missing)}"
            )
    return errors


def path_is_writable(path_value: str) -> bool:
    try:
        path = Path(path_value)
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".security_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False
