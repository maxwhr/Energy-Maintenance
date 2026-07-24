from __future__ import annotations


class SecuritySettings:
    SECRET_KEY: str = "change-this-secret-in-production"
    ADMIN_PASSWORD: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    ALGORITHM: str = "HS256"

    SECURITY_REQUIRE_STRONG_PRODUCTION_CONFIG: bool = True
    SECURITY_MIN_SECRET_KEY_LENGTH: int = 32
    SECURITY_MIN_ADMIN_PASSWORD_LENGTH: int = 10
    SECURITY_MAX_REQUEST_BODY_MB: int = 20
    SECURITY_MAX_JSON_BODY_MB: int = 5

    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 120
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_EXEMPT_PATHS: str = (
        "/api/health,/api/system/status,/docs,/openapi.json"
    )

    CORS_ALLOWED_ORIGINS: str = (
        "http://127.0.0.1:8010,http://localhost:8010,"
        "http://127.0.0.1:5173,http://localhost:5173"
    )
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: str = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    CORS_ALLOW_HEADERS: str = "Authorization,Content-Type"

    SECURITY_SCAN_EXCLUDE_DIRS: str = (
        "node_modules,.venv,dist,backend/static/frontend/assets,"
        "delivery,delivery_staging,.git"
    )
    SECURITY_SCAN_ALLOW_ENV_FILE: bool = True
