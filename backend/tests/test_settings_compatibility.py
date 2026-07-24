from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.retrieval_lab_config import RetrievalLabSettings
from app.core.security_config import (
    SecurityConfigError,
    enforce_startup_security,
)


EXPECTED_FIELD_COUNT = 252
EXPECTED_FIELD_DIGEST = (
    "39229bf9fa20d981f5f16b5253fdec8fe165f7d4aa9409f7002d69827fdf1a6b"
)
EXPECTED_DEFAULT_DIGEST = (
    "07e801162a55fccbf3c8c9cff194cd9db5e35fdbbe5d1206fd3665285347f725"
)


def _field_digest() -> str:
    value = "\n".join(sorted(Settings.model_fields)).encode()
    return hashlib.sha256(value).hexdigest()


def _default_digest() -> str:
    defaults = {
        name: field.default for name, field in Settings.model_fields.items()
    }
    value = json.dumps(
        defaults,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(value).hexdigest()


def _production_settings(tmp_path, **overrides) -> Settings:
    values = {
        "APP_ENV": "production",
        "DEBUG": False,
        "SECRET_KEY": "S" * 40,
        "ADMIN_PASSWORD": "LocalOnly-Strong-Password",
        "SECURITY_REQUIRE_STRONG_PRODUCTION_CONFIG": True,
        "DATABASE_URL": (
            "postgresql+psycopg://ci_user@127.0.0.1:55432/"
            "energy_maintenance_ci"
        ),
        "UPLOAD_DIR": str(tmp_path / "uploads"),
        "LOG_DIR": str(tmp_path / "logs"),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_settings_field_names_match_pre_split_snapshot() -> None:
    assert len(Settings.model_fields) == EXPECTED_FIELD_COUNT
    assert _field_digest() == EXPECTED_FIELD_DIGEST


def test_settings_defaults_match_pre_split_snapshot() -> None:
    assert _default_digest() == EXPECTED_DEFAULT_DIGEST
    assert Settings.model_fields["PORT"].default == 8000
    assert Settings.model_fields["RETRIEVAL_DEFAULT_MODE"].default == "keyword"
    assert Settings.model_config["extra"] == "ignore"
    assert Settings.model_config["env_file"] == ".env"


def test_database_url_can_be_overridden_by_environment(monkeypatch) -> None:
    test_url = (
        "postgresql+psycopg://ci_user@127.0.0.1:55432/"
        "energy_maintenance_ci"
    )
    monkeypatch.setenv("DATABASE_URL", test_url)
    assert Settings(_env_file=None).DATABASE_URL == test_url


def test_production_rejects_placeholder_secret_key() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            APP_ENV="production",
            SECRET_KEY="change-this-secret-in-production",
        )
    assert "SECRET_KEY must be replaced" in str(exc_info.value)


def test_production_accepts_strong_secret_and_admin_password(tmp_path) -> None:
    settings = _production_settings(tmp_path)
    enforce_startup_security(settings)


def test_csv_settings_are_parsed_compatibly() -> None:
    settings = Settings(
        _env_file=None,
        ALLOWED_DOCUMENT_EXTENSIONS="TXT, md,PDF",
        CORS_ALLOW_METHODS="GET, POST ,OPTIONS",
        RATE_LIMIT_EXEMPT_PATHS="/api/health, /docs",
    )
    assert settings.allowed_document_extensions == ["txt", "md", "pdf"]
    assert settings.cors_allow_methods == ["GET", "POST", "OPTIONS"]
    assert settings.rate_limit_exempt_paths == ["/api/health", "/docs"]


def test_retrieval_lab_remains_disabled_by_default() -> None:
    assert RetrievalLabSettings(_env_file=None).ENABLE_RETRIEVAL_LAB is False


def test_external_providers_remain_disabled_by_default() -> None:
    for field_name in (
        "CLOUD_LLM_ENABLED",
        "MINIMAX_ENABLED",
        "MIMO_ENABLED",
        "OCR_API_ENABLED",
        "EMBEDDING_ENABLED",
        "DASHVECTOR_ENABLED",
        "DASHSCOPE_RERANK_ENABLED",
        "RERANK_ENABLED",
    ):
        assert Settings.model_fields[field_name].default is False


def test_incomplete_enabled_provider_fails_production_validation(
    tmp_path,
) -> None:
    settings = _production_settings(
        tmp_path,
        CLOUD_LLM_ENABLED=True,
        CLOUD_LLM_API_KEY="",
        CLOUD_LLM_BASE_URL="",
        CLOUD_LLM_MODEL="",
    )
    with pytest.raises(SecurityConfigError) as exc_info:
        enforce_startup_security(settings)
    message = str(exc_info.value)
    assert "Cloud LLM is enabled but not fully configured" in message
    assert "CLOUD_LLM_API_KEY" in message
    assert "CLOUD_LLM_BASE_URL" in message
    assert "CLOUD_LLM_MODEL" in message


def test_legacy_task_flags_drive_product_semantic_aliases(monkeypatch) -> None:
    monkeypatch.setenv("TASK25B_ALLOW_REAL_API", "true")
    monkeypatch.setenv("TASK25C_ALLOW_REAL_API", "true")
    settings = Settings(_env_file=None)
    assert settings.TASK25B_ALLOW_REAL_API is True
    assert settings.TASK25C_ALLOW_REAL_API is True
    assert settings.EXTERNAL_MODEL_CALLS_ALLOWED is True
    assert settings.MULTIMODAL_EXTERNAL_CALLS_ALLOWED is True


def test_get_settings_cache_clear_reloads_environment(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_NAME", "Energy-Maintenance-Config-Test")
    try:
        assert get_settings().APP_NAME == "Energy-Maintenance-Config-Test"
        monkeypatch.setenv("APP_NAME", "Energy-Maintenance-Config-Test-Reloaded")
        assert get_settings().APP_NAME == "Energy-Maintenance-Config-Test"
        get_settings.cache_clear()
        assert get_settings().APP_NAME == (
            "Energy-Maintenance-Config-Test-Reloaded"
        )
    finally:
        get_settings.cache_clear()


def test_configuration_errors_do_not_expose_secret_values(tmp_path) -> None:
    secret_marker = "Sensitive-Key-Marker-Do-Not-Expose"
    settings = _production_settings(
        tmp_path,
        CLOUD_LLM_ENABLED=True,
        CLOUD_LLM_API_KEY=secret_marker,
        CLOUD_LLM_BASE_URL="",
        CLOUD_LLM_MODEL="",
    )
    with pytest.raises(SecurityConfigError) as exc_info:
        enforce_startup_security(settings)
    assert secret_marker not in str(exc_info.value)
