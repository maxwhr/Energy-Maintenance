from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.core.settings.validation import (
    PLACEHOLDER_VALUES,
    WEAK_ADMIN_PASSWORDS,
    is_configured_secret,
    path_is_writable,
    provider_configuration_errors,
)


@dataclass(frozen=True)
class SecurityValidationResult:
    status: str
    errors: list[str]
    warnings: list[str]


class SecurityConfigError(RuntimeError):
    pass


def validate_security_config(settings: Settings) -> SecurityValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    app_env = settings.APP_ENV.strip().lower()
    production = app_env == "production"

    if not is_configured_secret(settings.SECRET_KEY):
        errors.append("SECRET_KEY is missing or uses a placeholder value")
    elif len(settings.SECRET_KEY) < settings.SECURITY_MIN_SECRET_KEY_LENGTH:
        errors.append(
            f"SECRET_KEY is shorter than SECURITY_MIN_SECRET_KEY_LENGTH={settings.SECURITY_MIN_SECRET_KEY_LENGTH}"
        )

    if not settings.DATABASE_URL.startswith("postgresql"):
        errors.append("DATABASE_URL must use PostgreSQL")
    if "sqlite" in settings.DATABASE_URL.lower():
        errors.append("DATABASE_URL must not use SQLite")
    if production and settings.DEBUG:
        errors.append("DEBUG must be false in production")

    if not is_configured_secret(settings.ADMIN_PASSWORD):
        if production:
            errors.append("ADMIN_PASSWORD must be explicitly configured in production")
        else:
            warnings.append("ADMIN_PASSWORD is not configured; local scripts may use development fallback")
    elif settings.ADMIN_PASSWORD.strip().lower() in WEAK_ADMIN_PASSWORDS:
        errors.append("ADMIN_PASSWORD uses a weak value")
    elif len(settings.ADMIN_PASSWORD) < settings.SECURITY_MIN_ADMIN_PASSWORD_LENGTH:
        errors.append(
            "ADMIN_PASSWORD is shorter than "
            f"SECURITY_MIN_ADMIN_PASSWORD_LENGTH={settings.SECURITY_MIN_ADMIN_PASSWORD_LENGTH}"
        )

    origins = settings.cors_allowed_origins
    if "*" in origins:
        errors.append("CORS_ALLOWED_ORIGINS must not contain '*'")
    if production and not origins:
        errors.append("CORS_ALLOWED_ORIGINS must be configured in production")

    if settings.SECURITY_MAX_REQUEST_BODY_MB <= 0:
        errors.append("SECURITY_MAX_REQUEST_BODY_MB must be greater than zero")
    if settings.SECURITY_MAX_JSON_BODY_MB <= 0:
        errors.append("SECURITY_MAX_JSON_BODY_MB must be greater than zero")
    if settings.RATE_LIMIT_ENABLED and settings.RATE_LIMIT_REQUESTS <= 0:
        errors.append("RATE_LIMIT_REQUESTS must be greater than zero when rate limiting is enabled")

    if production and not path_is_writable(settings.UPLOAD_DIR):
        errors.append("UPLOAD_DIR is not writable")
    if production and not path_is_writable(settings.LOG_DIR):
        errors.append("LOG_DIR is not writable")

    errors.extend(provider_configuration_errors(settings))

    if errors and production and settings.SECURITY_REQUIRE_STRONG_PRODUCTION_CONFIG:
        return SecurityValidationResult(status="failed", errors=errors, warnings=warnings)
    if errors:
        warnings.extend(errors)
    return SecurityValidationResult(status="passed" if not warnings else "passed_with_warnings", errors=[], warnings=warnings)


def enforce_startup_security(settings: Settings) -> None:
    result = validate_security_config(settings)
    if settings.APP_ENV.strip().lower() == "production" and result.status == "failed":
        raise SecurityConfigError("; ".join(result.errors))


def collect_security_status(settings: Settings) -> dict[str, Any]:
    validation = validate_security_config(settings)
    external_provider_configured = any(
        [
            settings.DASHVECTOR_ENABLED and is_configured_secret(settings.DASHVECTOR_API_KEY),
            settings.EMBEDDING_ENABLED and is_configured_secret(settings.EMBEDDING_API_KEY),
            settings.CLOUD_LLM_ENABLED and is_configured_secret(settings.CLOUD_LLM_API_KEY),
            settings.MIMO_ENABLED and is_configured_secret(settings.MIMO_API_KEY),
            settings.OCR_API_ENABLED and is_configured_secret(settings.OCR_API_KEY),
            settings.DASHSCOPE_RERANK_ENABLED and is_configured_secret(settings.DASHSCOPE_API_KEY),
        ]
    )
    external_real_call_enabled = bool(settings.EXTERNAL_REAL_CALLS_ENABLED and external_provider_configured)
    return {
        "status": validation.status,
        "warnings": validation.warnings,
        "app_env": settings.APP_ENV,
        "production_guard_enabled": settings.SECURITY_REQUIRE_STRONG_PRODUCTION_CONFIG,
        "production_validation_status": validation.status,
        "production_validation_warnings": validation.warnings,
        "debug_enabled": settings.DEBUG,
        "cors_origin_policy": "restricted" if settings.cors_allowed_origins and "*" not in settings.cors_allowed_origins else "invalid",
        "cors_configured": bool(settings.cors_allowed_origins) and "*" not in settings.cors_allowed_origins,
        "cors_allow_credentials": settings.CORS_ALLOW_CREDENTIALS,
        "rate_limit_enabled": settings.RATE_LIMIT_ENABLED,
        "rate_limit_requests": settings.RATE_LIMIT_REQUESTS,
        "rate_limit_window_seconds": settings.RATE_LIMIT_WINDOW_SECONDS,
        "request_size_limit_enabled": settings.SECURITY_MAX_REQUEST_BODY_MB > 0,
        "max_request_body_mb": settings.SECURITY_MAX_REQUEST_BODY_MB,
        "max_json_body_mb": settings.SECURITY_MAX_JSON_BODY_MB,
        "secret_key_configured": is_configured_secret(settings.SECRET_KEY),
        "secret_key_min_length_ok": len(settings.SECRET_KEY or "") >= settings.SECURITY_MIN_SECRET_KEY_LENGTH,
        "admin_password_configured": is_configured_secret(settings.ADMIN_PASSWORD),
        "database_uses_postgresql": settings.DATABASE_URL.startswith("postgresql"),
        "log_dir_configured": bool(str(settings.LOG_DIR).strip()),
        "dashvector_key_configured": is_configured_secret(settings.DASHVECTOR_API_KEY),
        "embedding_key_configured": is_configured_secret(settings.EMBEDDING_API_KEY),
        "cloud_llm_key_configured": is_configured_secret(settings.CLOUD_LLM_API_KEY),
        "mimo_key_configured": is_configured_secret(settings.MIMO_API_KEY),
        "ocr_key_configured": is_configured_secret(settings.OCR_API_KEY),
        "dashscope_rerank_key_configured": is_configured_secret(settings.DASHSCOPE_API_KEY),
        "dashscope_rerank_enabled": settings.DASHSCOPE_RERANK_ENABLED,
        "local_llm_enabled": settings.LOCAL_LLM_ENABLED,
        "external_provider_configured": external_provider_configured,
        "external_real_call_enabled": external_real_call_enabled,
        "external_real_call_status": "enabled" if external_real_call_enabled else "blocked",
    }
