from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import Settings, get_settings  # noqa: E402
from app.core.security_config import collect_security_status, validate_security_config  # noqa: E402


def main() -> int:
    settings = get_settings()
    current = collect_security_status(settings)

    production_bad = Settings(
        APP_ENV="production",
        SECRET_KEY="short",
        ADMIN_PASSWORD="admin",
        DATABASE_URL="sqlite:///bad.db",
        CORS_ALLOWED_ORIGINS="*",
    )
    bad_result = validate_security_config(production_bad)
    if bad_result.status != "failed":
        raise AssertionError("insecure production settings must fail validation")

    development_result = validate_security_config(settings)
    if settings.APP_ENV != "production" and development_result.status not in {"passed", "passed_with_warnings"}:
        raise AssertionError("development settings must not be blocked by production guard")

    required_keys = {
        "app_env",
        "cors_configured",
        "rate_limit_enabled",
        "request_size_limit_enabled",
        "secret_key_configured",
        "admin_password_configured",
        "dashvector_key_configured",
        "embedding_key_configured",
        "cloud_llm_key_configured",
        "mimo_key_configured",
        "ocr_key_configured",
        "external_real_call_status",
    }
    missing = sorted(required_keys.difference(current))
    if missing:
        raise AssertionError(f"security status missing keys: {missing}")

    result = {
        "status": "passed",
        "app_env": current["app_env"],
        "production_guard_enabled": current["production_guard_enabled"],
        "current_validation_status": current["production_validation_status"],
        "insecure_production_rejected": True,
        "cors_configured": current["cors_configured"],
        "rate_limit_enabled": current["rate_limit_enabled"],
        "request_size_limit_enabled": current["request_size_limit_enabled"],
        "external_real_call_status": current["external_real_call_status"],
        "secret_key_configured": current["secret_key_configured"],
        "admin_password_configured": current["admin_password_configured"],
        "key_values_printed": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "failed", "error": str(exc), "key_values_printed": False}, ensure_ascii=False))
        raise SystemExit(1)
